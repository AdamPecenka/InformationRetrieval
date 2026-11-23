# Host side (Spark): athletes + aggregated results + best wiki match -> docs.tsv.
# TSV, not parquet, so the container needs no Spark.
import os

from pyspark.sql import Column, DataFrame, Window
from pyspark.sql import functions as F

from common.log import log_add, log_error, log_info
from common.tsv import format_row
from constants.common import LIST_SEPARATOR
from constants.lucene import LUCENE_DOC_COLUMNS
from regexes.join import JOIN_YEAR_REGEX
from wiki.audit import read_athletes
from wiki.dump import build_spark
from wiki.inputs import require_dir, require_file

SAMPLE_ROWS: int = 5


def _non_empty(column: Column) -> Column:
    """Trimmed, null if blank."""
    return F.when(F.length(F.trim(column)) > 0, F.trim(column))


def _year(column: Column) -> Column:
    """"1985-06-30" / "1985" -> "1985", else null."""
    return F.when(column.rlike(JOIN_YEAR_REGEX), F.substring(column, 1, 4))


def _distinct_list(column: Column) -> Column:
    return F.concat_ws(LIST_SEPARATOR, F.sort_array(F.collect_set(_non_empty(column))))


def aggregate_results(results: DataFrame) -> DataFrame:
    """One row per athlete."""
    def pairs(kind: str) -> Column:
        has_medal = _non_empty(F.col("medal")).isNotNull() & _non_empty(F.col(kind)).isNotNull()
        pair = F.when(has_medal, F.lower(F.concat_ws(":", F.trim(F.col(kind)), F.trim(F.col("medal")))))
        return F.concat_ws(LIST_SEPARATOR, F.sort_array(F.collect_set(pair)))

    return results.groupBy("athlete_id").agg(
        _distinct_list(F.col("sport")).alias("sports"),
        _distinct_list(F.col("discipline")).alias("disciplines"),
        _distinct_list(F.col("event")).alias("events"),
        _distinct_list(F.col("games")).alias("games"),
        _distinct_list(F.col("season")).alias("seasons"),
        _distinct_list(F.col("year")).alias("result_years"),
        _distinct_list(F.col("medal")).alias("result_medals"),
        pairs("sport").alias("sport_medals"),
        pairs("discipline").alias("discipline_medals"),
    )


def best_wiki_match(joined: DataFrame) -> DataFrame:
    """Lowest tier, ties -> smaller page id."""
    ranking = Window.partitionBy("athlete_id").orderBy(F.col("tier").asc(), F.col("page_id").asc())

    return (
        joined
        .withColumn("match_rank", F.row_number().over(ranking))
        .filter(F.col("match_rank") == 1)
        .select(
            "athlete_id",
            F.col("page_id").alias("wiki_page_id"),
            F.col("tier").alias("wiki_tier"),
            F.col("title").alias("wiki_title"),
            F.col("sport").alias("wiki_sport"),
            F.col("nationality").alias("wiki_nationality"),
            F.col("birth_place").alias("wiki_birth_place"),
            F.col("death_place").alias("wiki_death_place"),
            "wiki_height_cm",
            "wiki_weight_kg",
            F.col("lead").alias("wiki_lead"),
            F.col("body").alias("wiki_body"),
        )
    )


def report_gaps(merged: DataFrame) -> None:
    """Must run before fill_from_wikipedia."""
    gaps = {
        "height_cm": F.col("height_cm").cast("double").isNull() & F.col("wiki_height_cm").isNotNull(),
        "weight_kg": F.col("weight_kg").cast("double").isNull() & F.col("wiki_weight_kg").isNotNull(),
        "born_place": _non_empty(F.col("born_place")).isNull() & _non_empty(F.col("wiki_birth_place")).isNotNull(),
        "died_place": _non_empty(F.col("died_place")).isNull() & _non_empty(F.col("wiki_death_place")).isNotNull(),
    }

    for name, condition in gaps.items():
        log_add(f"{name}: {merged.filter(condition).count()} athletes filled from Wikipedia")


def fill_from_wikipedia(merged: DataFrame) -> DataFrame:
    """Olympedia first, Wikipedia as fallback."""
    return (
        merged
        .withColumn("height_cm", F.round(F.coalesce(F.col("height_cm").cast("double"), F.col("wiki_height_cm"))).cast("int"))
        .withColumn("weight_kg", F.round(F.coalesce(F.col("weight_kg").cast("double"), F.col("wiki_weight_kg"))).cast("int"))
        .withColumn("born_place", F.coalesce(_non_empty(F.col("born_place")), _non_empty(F.col("wiki_birth_place"))))
        .withColumn("died_place", F.coalesce(_non_empty(F.col("died_place")), _non_empty(F.col("wiki_death_place"))))
    )


def build_documents(athletes: DataFrame, results: DataFrame, joined: DataFrame) -> DataFrame:
    merged = (
        athletes
        .join(aggregate_results(results), "athlete_id", "left")
        .join(best_wiki_match(joined), "athlete_id", "left")
    ).cache()

    report_gaps(merged)

    filled = (
        fill_from_wikipedia(merged)
        .withColumn("born_year", _year(F.col("born_date")))
        .withColumn("died_year", _year(F.col("died_date")))
    )

    # null -> "", every row gets every column.
    return filled.select(*[F.coalesce(F.col(column).cast("string"), F.lit("")).alias(column) for column in LUCENE_DOC_COLUMNS])


def write_documents(documents: DataFrame, path: str) -> int:
    """Collected on the driver, written to .tmp and swapped in."""
    rows = documents.orderBy(F.col("athlete_id").cast("int")).collect()
    directory = os.path.dirname(path)

    if directory != "":
        os.makedirs(directory, exist_ok=True)

    with open(path + ".tmp", "w", encoding="utf-8", newline="") as handle:
        handle.write(format_row(LUCENE_DOC_COLUMNS))

        for row in rows:
            handle.write(format_row([row[column] for column in LUCENE_DOC_COLUMNS]))

    os.replace(path + ".tmp", path)
    return len(rows)


def run_lucene_export(athletes_path: str, results_path: str, joined_path: str, output_path: str) -> int:
    if not require_file(athletes_path) or not require_file(results_path) or not require_dir(joined_path):
        return 1

    spark = build_spark(app_name="vinf-lucene-export", with_xml=False)

    try:
        ui_url = spark.sparkContext.uiWebUrl

        if ui_url is not None:
            log_info(f"spark UI: {ui_url}")

        athletes = read_athletes(spark, athletes_path)
        results = read_athletes(spark, results_path)
        joined = spark.read.parquet(joined_path)

        athlete_count = athletes.count()
        log_info(f"athletes: {athlete_count}, result rows: {results.count()}, joined pairs: {joined.count()}")

        documents = build_documents(athletes, results, joined).cache()
        document_count = documents.count()

        if document_count != athlete_count:
            log_error(f"{document_count} documents for {athlete_count} athletes, a join duplicated or dropped rows")
            return 1

        with_wiki = documents.filter(F.col("wiki_page_id") != "").count()
        with_lead = documents.filter(F.col("wiki_lead") != "").count()
        with_body = documents.filter(F.col("wiki_body") != "").count()
        with_results = documents.filter(F.col("sports") != "").count()
        log_info(f"with results: {with_results}, with a Wikipedia page: {with_wiki} (lead {with_lead}, body {with_body})")

        written = write_documents(documents, output_path)
        log_add(f"{written} documents written to {output_path}")

        documents.select("athlete_id", "full_name", "born_year", "sport_medals", "wiki_title", "wiki_tier").show(SAMPLE_ROWS, truncate=40)
    finally:
        spark.stop()

    return 0