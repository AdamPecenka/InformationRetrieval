import os
from typing import Optional

from pyspark.sql import Column, DataFrame, Row, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, StringType, StructField, StructType

import constants
from common.log import log_add, log_alert, log_error, log_info
from extractor.engine import extract_page
from extractor.storage import list_pages, read_page

ATHLETE_STRUCT: StructType = StructType([StructField(column, StringType(), True) for column in constants.ATHLETE_COLUMNS])
RESULT_STRUCT: StructType = StructType([StructField(column, StringType(), True) for column in constants.RESULT_COLUMNS])
PARSED_SCHEMA: StructType = StructType([
    StructField("athlete", ATHLETE_STRUCT, True),
    StructField("results", ArrayType(RESULT_STRUCT), True),
    StructField("warnings", ArrayType(StringType()), True),
    StructField("error", StringType(), True),
])

ParsedPage = tuple[Optional[tuple[str, ...]], list[tuple[str, ...]], list[str], Optional[str]]


def _parse_page(athlete_id: str, content: Optional[bytearray]) -> ParsedPage:
    """The UDF body. One broken page must not stop the job, so an exception becomes the `error` field."""
    try:
        if content is None:
            return None, [], [], "no content"

        page_html = bytes(content).decode("utf-8", errors="replace")
        athlete, results, warnings = extract_page(page_html, athlete_id)
        athlete_values = tuple(athlete[column] for column in constants.ATHLETE_COLUMNS)
        result_values = [tuple(result[column] for column in constants.RESULT_COLUMNS) for result in results]
        return athlete_values, result_values, warnings, None
    except Exception as error:
        return None, [], [], f"{type(error).__name__}: {error}"


_parse_udf = F.udf(_parse_page, PARSED_SCHEMA)


def parse_pages(pages: DataFrame) -> DataFrame:
    """pages: (path, content). Returns (athlete_id, parsed) with parsed = (athlete, results, warnings, error)."""
    athlete_id: Column = F.regexp_extract(F.col("path"), constants.OLYMPEDIA_FILE_ID_REGEX, 1)

    return (
        pages
        .repartition(constants.OLYMPEDIA_SPARK_PARTITIONS)
        .select(athlete_id.alias("athlete_id"), F.col("content"))
        .select("athlete_id", _parse_udf(F.col("athlete_id"), F.col("content")).alias("parsed"))
    )


def _values(row: Row, columns: list[str]) -> list[str]:
    return [row[column] if row[column] is not None else "" for column in columns]


def load_rows(
    spark: SparkSession, athletes_path: str, results_path: str,
) -> tuple[dict[str, dict[str, str]], dict[str, list[dict[str, str]]]]:
    """The written Parquet as dictionaries, for --verify. The result rows of one athlete keep their order."""
    athletes_by_id: dict[str, dict[str, str]] = {}
    results_by_id: dict[str, list[dict[str, str]]] = {}

    for row in spark.read.parquet(athletes_path).collect():
        athletes_by_id[row["athlete_id"]] = dict(zip(constants.ATHLETE_COLUMNS, _values(row, constants.ATHLETE_COLUMNS)))

    for row in spark.read.parquet(results_path).collect():
        results_by_id.setdefault(row["athlete_id"], []).append(dict(zip(constants.RESULT_COLUMNS, _values(row, constants.RESULT_COLUMNS))))

    return athletes_by_id, results_by_id


def verify(athletes_by_id: dict[str, dict[str, str]], results_by_id: dict[str, list[dict[str, str]]]) -> bool:
    """Parse every page again with the plain extractor and compare with what Spark produced."""
    identical = 0
    plain_failed = 0
    differing: list[str] = []
    details: list[str] = []
    pages = list_pages()

    for path in pages:
        athlete_id = os.path.splitext(os.path.basename(path))[0]

        try:
            athlete, results, _ = extract_page(read_page(path), athlete_id)
        except Exception:
            plain_failed += 1

            if athlete_id in athletes_by_id:
                differing.append(athlete_id)
                details.append(f"{athlete_id}: plain extractor failed, Spark produced a row")

            continue

        spark_athlete = athletes_by_id.get(athlete_id)
        spark_results = results_by_id.get(athlete_id, [])

        if spark_athlete == athlete and spark_results == results:
            identical += 1
            continue

        differing.append(athlete_id)

        if spark_athlete is None:
            details.append(f"{athlete_id}: missing from the Spark output")
        elif spark_athlete != athlete:
            columns = [column for column in constants.ATHLETE_COLUMNS if spark_athlete[column] != athlete[column]]
            details.append(f"{athlete_id}: athlete columns differ: {columns}")
        else:
            details.append(f"{athlete_id}: result rows differ ({len(spark_results)} Spark, {len(results)} plain)")

    log_info(f"verify: {len(pages)} pages, {identical} identical, {len(differing)} different, {plain_failed} failed in the plain extractor")

    for line in details[:constants.EXTRACT_MAX_PAGE_WARNINGS]:
        log_alert(f"verify: {line}")

    return len(differing) == 0


def run_spark_extractor(run_verify: bool) -> int:
    if not os.path.isdir(constants.RAW_ATHLETES_DIR):
        log_error(f"no athlete pages in {constants.RAW_ATHLETES_DIR}, run the crawler first")
        return 1

    from wiki.dump import build_spark

    spark = build_spark(app_name="vinf-olympedia-extract", with_xml=False)
    exit_code = 0

    try:
        ui_url = spark.sparkContext.uiWebUrl

        if ui_url is not None:
            log_info(f"spark UI: {ui_url}")

        pages = (
            spark.read.format("binaryFile")
            .option("pathGlobFilter", "*.html")
            .load(constants.RAW_ATHLETES_DIR)
            .select("path", "content")
        )
        parsed = parse_pages(pages).cache()
        total = parsed.count()
        stored = len(list_pages())

        if total != stored:
            # binaryFile does not return zero-byte files. The crawler never stores an empty page, so this points to a damaged download.
            log_alert(f"{stored} pages are stored but Spark read {total}: empty files are skipped, check data/raw/athletes")

        failed = parsed.filter(F.col("parsed.error").isNotNull())
        failed_count = failed.count()
        log_info(f"pages parsed: {total}, failed: {failed_count}")

        if failed_count > 0:
            exit_code = 1
            failed.select("athlete_id", F.col("parsed.error").alias("error")).show(constants.EXTRACT_MAX_PAGE_WARNINGS, truncate=False)

        good = parsed.filter(F.col("parsed.error").isNull())
        athletes = good.select("parsed.athlete.*")
        results = good.select(F.explode("parsed.results").alias("result")).select("result.*")

        log_add(f"writing parquet to {constants.OLYMPEDIA_ATHLETES_PARQUET_PATH} and {constants.OLYMPEDIA_RESULTS_PARQUET_PATH}")
        athletes.write.mode("overwrite").parquet(constants.OLYMPEDIA_ATHLETES_PARQUET_PATH)
        results.write.mode("overwrite").parquet(constants.OLYMPEDIA_RESULTS_PARQUET_PATH)

        warnings = good.select(F.explode("parsed.warnings").alias("warning")).groupBy("warning").count().orderBy(F.desc("count"))

        for row in warnings.collect():
            log_alert(f"{row['count']} pages: {row['warning']}")

        if run_verify:
            athletes_by_id, results_by_id = load_rows(
                spark, constants.OLYMPEDIA_ATHLETES_PARQUET_PATH, constants.OLYMPEDIA_RESULTS_PARQUET_PATH,
            )

            if not verify(athletes_by_id, results_by_id):
                exit_code = 1
    finally:
        spark.stop()

    return exit_code