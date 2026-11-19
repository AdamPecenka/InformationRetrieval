"""Recall check for the relevance filter, against the Olympedia athletes we actually have.

Idea: take every Wikipedia page whose title equals an Olympedia athlete name (a disambiguation suffix
like " (swimmer)" is ignored) and see which of those pages the filter dropped. A dropped page that
still talks about the Olympics is a likely miss and is printed with a snippet.

The title match is exact (lower-cased, no diacritic folding), so it finds a lower bound of the real
name matches. It checks the filter, it is not the join.
"""

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from common.log import log_alert, log_error, log_info
from wiki.dump import build_spark
from wiki.inputs import require_dir, require_file

REQUIRED_COLUMNS: list[str] = ["athlete_id", "used_name", "full_name"]
EMPTY_NAMES: list[str] = ["", "null", "none"]
SAMPLE_SIZE: int = 25
SNIPPET_REGEX: str = r"(?is)(.{0,70}olymp.{0,70})"
OLYMPIC_MENTION_REGEX: str = r"(?i)olymp"


def read_athletes(spark: SparkSession, path: str) -> DataFrame:
    # The project's TSV writer collapses tabs and newlines inside fields and never quotes,
    # so quoting must be off or a stray " in a biography would swallow following rows.
    return (
        spark.read
        .option("sep", "\t")
        .option("header", True)
        .option("quote", "")
        .csv(path)
    )


def athlete_name_keys(athletes: DataFrame) -> DataFrame:
    used = athletes.select("athlete_id", F.col("used_name").alias("name"))
    full = athletes.select("athlete_id", F.col("full_name").alias("name"))

    return (
        used.unionByName(full)
        .withColumn("name_key", F.lower(F.trim(F.col("name"))))
        .filter(F.col("name_key").isNotNull() & ~F.col("name_key").isin(EMPTY_NAMES))
        .select("athlete_id", "name_key")
        .distinct()
    )


def title_candidates(pages: DataFrame, names: DataFrame) -> DataFrame:
    """(page_id, title, athlete_id) for pages whose title, minus a trailing (...), is an athlete name."""
    keyed = pages.withColumn(
        "name_key",
        F.lower(F.trim(F.regexp_replace(F.col("title"), r"\s*\([^)]*\)$", ""))),
    )

    return keyed.join(F.broadcast(names), "name_key").select("page_id", "title", "athlete_id")


def report_id_coverage(athletes: DataFrame, candidates: DataFrame, relevant: DataFrame) -> None:
    """How many Olympedia athletes can be joined exactly, through the Olympedia id found in a wiki page."""
    if "olympedia_id" not in relevant.columns:
        log_alert("the relevant parquet has no olympedia_id column: rerun wiki-filter with the current code")
        return

    page_ids = (
        relevant
        .filter(F.col("olympedia_id").isNotNull())
        .select("page_id", F.col("olympedia_id").alias("athlete_id"))
    )
    by_id = athletes.select("athlete_id").distinct().join(page_ids, "athlete_id").cache()

    athletes_by_id = by_id.select("athlete_id").distinct().count()
    pages_by_id = by_id.select("page_id").distinct().count()
    by_title_only_missed = (
        by_id.select("athlete_id").distinct()
        .join(candidates.select("athlete_id").distinct(), "athlete_id", "left_anti")
        .count()
    )

    log_info(f"exact id join: {athletes_by_id} athletes matched to {pages_by_id} distinct wiki pages")
    log_info(f"  of those, found by id but NOT by same-title match: {by_title_only_missed}")


def run_audit(athletes_path: str, pages_path: str, relevant_path: str) -> int:
    if not require_file(athletes_path):
        return 1

    if not require_dir(pages_path):
        return 1

    if not require_dir(relevant_path):
        return 1

    spark = build_spark("vinf-wiki-audit", with_xml=False)

    try:
        athletes = read_athletes(spark, athletes_path)
        missing = [name for name in REQUIRED_COLUMNS if name not in athletes.columns]

        if len(missing) > 0:
            log_error(f"missing columns in {athletes_path}: {missing}")
            return 1

        names = athlete_name_keys(athletes)
        athlete_total = athletes.select("athlete_id").distinct().count()

        full_pages = spark.read.parquet(pages_path)
        candidates = title_candidates(full_pages.select("page_id", "title"), names).cache()

        candidate_pages = candidates.select("page_id").distinct()
        kept_ids = spark.read.parquet(relevant_path).select("page_id")
        dropped_ids = candidate_pages.join(kept_ids, "page_id", "left_anti").cache()

        candidate_count = candidate_pages.count()
        dropped_count = dropped_ids.count()
        matched_athletes = candidates.select("athlete_id").distinct().count()

        log_info(f"athletes read: {athlete_total}")
        log_info(f"athletes with at least one same-title article: {matched_athletes}")
        log_info(f"same-title articles: {candidate_count}, kept by the filter: {candidate_count - dropped_count}, dropped: {dropped_count}")

        report_id_coverage(athletes, candidates, spark.read.parquet(relevant_path))

        if dropped_count == 0:
            log_info("nothing dropped among the title matches")
            return 0

        # Second read of the text column, restricted to the dropped candidates.
        dropped_text = (
            full_pages
            .join(F.broadcast(dropped_ids), "page_id", "left_semi")
            .select("page_id", "title", "wikitext")
            .filter(F.col("wikitext").rlike(OLYMPIC_MENTION_REGEX))
            .cache()
        )

        suspicious = dropped_text.count()
        log_info(f"dropped articles that mention the Olympics in their text: {suspicious}")
        log_info(f"dropped articles without any Olympic mention (likely namesakes): {dropped_count - suspicious}")

        if suspicious > 0:
            log_info(f"first {SAMPLE_SIZE} suspicious drops:")
            (
                dropped_text
                .select(
                    "page_id",
                    "title",
                    F.regexp_replace(F.regexp_extract(F.col("wikitext"), SNIPPET_REGEX, 1), r"\s+", " ").alias("snippet"),
                )
                .orderBy("page_id")
                .show(SAMPLE_SIZE, truncate=110)
            )
    finally:
        spark.stop()

    return 0