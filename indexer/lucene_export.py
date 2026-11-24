# Host side (Spark): athletes + aggregated results + best wiki match, plus the wiki_only pages -> docs.tsv.
# TSV, not parquet, so the container needs no Spark.
import os

from pyspark.sql import Column, DataFrame, Window
from pyspark.sql import functions as F

from common.log import log_add, log_alert, log_error, log_info
from common.tsv import format_row
from constants.common import LIST_SEPARATOR
from constants.join import JOIN_MATCH_BOTH, JOIN_MATCH_OLYMPEDIA_ONLY, JOIN_MATCH_WIKI_ONLY
from constants.lucene import LUCENE_DOC_COLUMNS, LUCENE_WIKI_DOC_PREFIX
from regexes.join import JOIN_TITLE_SUFFIX_REGEX, JOIN_YEAR_REGEX
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


def _doc_columns(frame: DataFrame) -> DataFrame:
    """Exactly LUCENE_DOC_COLUMNS as strings; null or missing -> ""."""
    selected: list[Column] = []

    for column in LUCENE_DOC_COLUMNS:
        if column in frame.columns:
            value = F.col(column).cast("string")
        else:
            value = F.lit(None).cast("string")

        selected.append(F.coalesce(value, F.lit("")).alias(column))

    return frame.select(*selected)


def athlete_documents(athletes: DataFrame, results: DataFrame, matched: DataFrame) -> DataFrame:
    """One document per athlete (both / olympedia_only)."""
    merged = (
        athletes
        .join(aggregate_results(results), "athlete_id", "left")
        .join(best_wiki_match(matched), "athlete_id", "left")
    ).cache()

    report_gaps(merged)

    match_type = F.when(F.col("wiki_page_id").isNotNull(), F.lit(JOIN_MATCH_BOTH)).otherwise(F.lit(JOIN_MATCH_OLYMPEDIA_ONLY))
    filled = (
        fill_from_wikipedia(merged)
        .withColumn("doc_id", F.col("athlete_id"))
        .withColumn("match_type", match_type)
        .withColumn("born_year", _year(F.col("born_date")))
        .withColumn("died_year", _year(F.col("died_date")))
    )

    return _doc_columns(filled)


def wiki_documents(wiki_only: DataFrame) -> DataFrame:
    """One document per wiki_only page, Olympedia-shaped columns filled from the Wikipedia side."""
    medals = F.col("olympic_gold") + F.col("olympic_silver") + F.col("olympic_bronze")

    documents = wiki_only.select(
        F.concat(F.lit(LUCENE_WIKI_DOC_PREFIX), F.col("page_id").cast("string")).alias("doc_id"),
        F.lit(JOIN_MATCH_WIKI_ONLY).alias("match_type"),
        F.trim(F.regexp_replace(F.col("title"), JOIN_TITLE_SUFFIX_REGEX, "")).alias("full_name"),
        F.col("birth_date").alias("born_date"),
        F.col("birth_place").alias("born_place"),
        F.col("death_date").alias("died_date"),
        F.col("death_place").alias("died_place"),
        F.round(F.col("wiki_height_cm")).cast("int").alias("height_cm"),
        F.round(F.col("wiki_weight_kg")).cast("int").alias("weight_kg"),
        F.col("olympic_gold").alias("medals_gold"),
        F.col("olympic_silver").alias("medals_silver"),
        F.col("olympic_bronze").alias("medals_bronze"),
        medals.alias("medals_total"),
        F.coalesce(F.col("infobox_year"), F.col("category_year")).alias("born_year"),
        _year(F.col("death_date")).alias("died_year"),
        F.col("page_id").alias("wiki_page_id"),
        F.col("title").alias("wiki_title"),
        F.col("sport").alias("wiki_sport"),
        F.col("nationality").alias("wiki_nationality"),
        F.col("lead").alias("wiki_lead"),
        F.col("body").alias("wiki_body"),
    )

    return _doc_columns(documents)


def write_documents(documents: DataFrame, path: str) -> int:
    """Streamed to the driver (wiki_only bodies don't fit a collect), written to .tmp and swapped in."""
    ordered = documents.orderBy(
        F.col("athlete_id").cast("int").asc_nulls_last(),
        F.col("wiki_page_id").cast("int").asc_nulls_last(),
    )
    directory = os.path.dirname(path)
    written = 0

    if directory != "":
        os.makedirs(directory, exist_ok=True)

    with open(path + ".tmp", "w", encoding="utf-8", newline="") as handle:
        handle.write(format_row(LUCENE_DOC_COLUMNS))

        for row in ordered.toLocalIterator():
            handle.write(format_row([row[column] for column in LUCENE_DOC_COLUMNS]))
            written += 1

    os.replace(path + ".tmp", path)
    return written


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
        full = spark.read.parquet(joined_path)

        if "match_type" not in full.columns:
            log_error(f"{joined_path} has no match_type column, pass the full join output (wiki-join --full-output)")
            return 1

        matched = full.filter(F.col("match_type") == JOIN_MATCH_BOTH)
        wiki_only = full.filter(F.col("match_type") == JOIN_MATCH_WIKI_ONLY)
        olympedia_only_rows = full.filter(F.col("match_type") == JOIN_MATCH_OLYMPEDIA_ONLY).count()

        athlete_count = athletes.count()
        wiki_only_count = wiki_only.count()
        log_info(f"athletes: {athlete_count}, result rows: {results.count()}, matched pairs: {matched.count()}, wiki_only pages: {wiki_only_count}")

        documents = athlete_documents(athletes, results, matched).unionByName(wiki_documents(wiki_only)).cache()
        document_count = documents.count()
        both_count = documents.filter(F.col("match_type") == JOIN_MATCH_BOTH).count()
        olympedia_only_count = documents.filter(F.col("match_type") == JOIN_MATCH_OLYMPEDIA_ONLY).count()
        log_info(f"documents: {document_count} = both {both_count} + olympedia_only {olympedia_only_count} + wiki_only {wiki_only_count}")

        if document_count != athlete_count + wiki_only_count:
            log_error(f"{document_count} documents, expected {athlete_count} athletes + {wiki_only_count} wiki_only, a join duplicated or dropped rows")
            return 1

        if olympedia_only_count != olympedia_only_rows:
            log_alert(f"{olympedia_only_count} olympedia_only documents but {olympedia_only_rows} olympedia_only rows in {joined_path}, athletes.tsv changed since wiki-join?")

        athlete_docs = documents.filter(F.col("match_type") != JOIN_MATCH_WIKI_ONLY)
        with_lead = athlete_docs.filter(F.col("wiki_lead") != "").count()
        with_body = athlete_docs.filter(F.col("wiki_body") != "").count()
        with_results = athlete_docs.filter(F.col("sports") != "").count()
        log_info(f"athletes with results: {with_results}, with a Wikipedia page: {both_count} (lead {with_lead}, body {with_body})")

        written = write_documents(documents, output_path)
        log_add(f"{written} documents written to {output_path}")

        documents.select("doc_id", "match_type", "full_name", "born_year", "sport_medals", "wiki_title", "wiki_tier").show(SAMPLE_ROWS, truncate=40)
    finally:
        spark.stop()

    return 0
