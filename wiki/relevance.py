"""Stage 2: keep articles where ANY flag fires; flags are kept as bool columns for auditing.

Flags: person_category, person_infobox, olympic_title, olympic_category, olympic_medal, olympedia_link
(regexes in regexes/wiki.py). Also adds olympedia_id_count / olympedia_id for the exact join.
"""

import os

from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F

from common.log import log_add, log_alert, log_error, log_info
from regexes.wiki import (
    WIKI_OLYMPEDIA_LINK_REGEX,
    WIKI_OLYMPEDIA_TEMPLATE_ID_REGEX,
    WIKI_OLYMPEDIA_URL_ID_REGEX,
    WIKI_OLYMPIC_CATEGORY_REGEX,
    WIKI_OLYMPIC_MEDAL_REGEX,
    WIKI_OLYMPIC_TITLE_REGEX,
    WIKI_PERSON_CATEGORY_REGEX,
    WIKI_PERSON_INFOBOX_REGEX,
)
from wiki.dump import build_spark
from wiki.inputs import require_dir

# (flag, source column, regex), cheapest first.
FLAG_RULES: list[tuple[str, str, str]] = [
    ("olympic_title", "title", WIKI_OLYMPIC_TITLE_REGEX),
    ("person_category", "wikitext", WIKI_PERSON_CATEGORY_REGEX),
    ("olympic_category", "wikitext", WIKI_OLYMPIC_CATEGORY_REGEX),
    ("person_infobox", "wikitext", WIKI_PERSON_INFOBOX_REGEX),
    ("olympic_medal", "wikitext", WIKI_OLYMPIC_MEDAL_REGEX),
    ("olympedia_link", "wikitext", WIKI_OLYMPEDIA_LINK_REGEX),
]

FLAG_COLUMNS: list[str] = [name for name, _, _ in FLAG_RULES]
PERSON_FLAGS: list[str] = ["person_category", "person_infobox"]
OLYMPIC_FLAGS: list[str] = ["olympic_title", "olympic_category", "olympic_medal", "olympedia_link"]

SAMPLE_SIZE: int = 15
SAMPLE_PER_FLAG: int = 5
SAMPLE_SEED: int = 7


def add_relevance_flags(articles: DataFrame) -> DataFrame:
    flagged = articles

    for name, source, pattern in FLAG_RULES:
        flagged = flagged.withColumn(name, F.col(source).rlike(pattern))

    return _add_olympedia_id(flagged)


def _extract_all(pattern: str) -> Column:
    # F.regexp_extract_all needs PySpark 3.5, the SQL function only 3.1. r'...' keeps backslashes intact.
    return F.expr(f"regexp_extract_all(wikitext, r'{pattern}', 1)")


def _add_olympedia_id(flagged: DataFrame) -> DataFrame:
    """olympedia_id_count: distinct ids cited (null without an Olympedia link).
    olympedia_id: set only for a person page citing exactly one id (lists / date pages cite many).
    """
    all_ids = F.array_distinct(F.concat(
        _extract_all(WIKI_OLYMPEDIA_URL_ID_REGEX),
        _extract_all(WIKI_OLYMPEDIA_TEMPLATE_ID_REGEX),
    ))
    is_person = F.col("person_category") | F.col("person_infobox")

    return (
        flagged
        .withColumn("olympedia_id_count", F.when(F.col("olympedia_link"), F.size(all_ids)))
        .withColumn("olympedia_id", F.when(is_person & (F.col("olympedia_id_count") == 1), all_ids[0]))
    )


def any_of(names: list[str]) -> Column:
    condition = F.col(names[0])

    for name in names[1:]:
        condition = condition | F.col(name)

    return condition


def keep_relevant(flagged: DataFrame) -> DataFrame:
    return flagged.filter(any_of(FLAG_COLUMNS))


def summarize(kept: DataFrame) -> dict[str, int]:
    """Per flag: pages it fires on, and pages kept only because of it. One pass."""
    person = any_of(PERSON_FLAGS)
    olympic = any_of(OLYMPIC_FLAGS)

    aggregations: list[Column] = [F.count(F.lit(1)).alias("kept")]

    for name in FLAG_COLUMNS:
        others = [other for other in FLAG_COLUMNS if other != name]

        aggregations.append(F.sum(F.col(name).cast("int")).alias(name))
        aggregations.append(F.sum((F.col(name) & ~any_of(others)).cast("int")).alias(f"only_{name}"))

    aggregations.append(F.sum((person & ~olympic).cast("int")).alias("person_not_olympic"))
    aggregations.append(F.sum((olympic & ~person).cast("int")).alias("olympic_not_person"))
    aggregations.append(F.sum(F.col("olympedia_id").isNotNull().cast("int")).alias("with_olympedia_id"))
    aggregations.append(F.countDistinct("olympedia_id").alias("distinct_olympedia_ids"))
    aggregations.append(F.sum((F.col("olympedia_id_count") > 1).cast("int")).alias("pages_citing_many_ids"))
    aggregations.append(F.sum((F.col("olympedia_id_count") == 1).cast("int")).alias("pages_citing_one_id"))

    row = kept.agg(*aggregations).first()
    counts: dict[str, int] = {}

    if row is None:
        return counts

    for key, value in row.asDict().items():
        if value is None:
            counts[key] = 0
        else:
            counts[key] = int(value)

    return counts


def _percent(part: int, whole: int) -> str:
    if whole == 0:
        return "0.0%"

    return f"{100.0 * part / whole:.1f}%"


def _log_counts(counts: dict[str, int], total: int) -> None:
    kept_count = counts["kept"]

    log_info(f"kept {kept_count} of {total} ({_percent(kept_count, total)})")
    log_info("  flag: pages where it fires / pages kept only because of it")

    for name in FLAG_COLUMNS:
        log_info(f"  {name}: {counts[name]} / {counts['only_' + name]}")

    log_info(f"  person signal, no Olympic signal: {counts['person_not_olympic']}")
    log_info(f"  Olympic signal, no person signal: {counts['olympic_not_person']}")
    log_info(f"  pages citing one Olympedia athlete id: {counts['pages_citing_one_id']}, many ids: {counts['pages_citing_many_ids']}")
    log_info(f"  pages given an Olympedia id (person page, one id): {counts['with_olympedia_id']} ({counts['distinct_olympedia_ids']} distinct ids)")


def _log_samples(kept: DataFrame) -> None:
    person = any_of(PERSON_FLAGS)
    olympic = any_of(OLYMPIC_FLAGS)

    log_info(f"random sample of {SAMPLE_SIZE} Olympic pages without a person signal:")
    (
        kept
        .filter(olympic & ~person)
        .select("title", F.rand(SAMPLE_SEED).alias("r"))
        .orderBy("r")
        .select("title")
        .limit(SAMPLE_SIZE)
        .show(SAMPLE_SIZE, truncate=False)
    )

    log_info("random sample of pages given an Olympedia id (check that they are the athletes themselves):")
    (
        kept
        .filter(F.col("olympedia_id").isNotNull())
        .select("title", "olympedia_id", F.rand(SAMPLE_SEED).alias("r"))
        .orderBy("r")
        .select("title", "olympedia_id")
        .limit(SAMPLE_SIZE)
        .show(SAMPLE_SIZE, truncate=False)
    )

    # What each rule alone catches -> is it worth keeping.
    for name in FLAG_COLUMNS:
        others = [other for other in FLAG_COLUMNS if other != name]
        only_this = kept.filter(F.col(name) & ~any_of(others)).select("title").limit(SAMPLE_PER_FLAG)
        titles = [row["title"] for row in only_this.collect()]

        if len(titles) > 0:
            log_info(f"  kept only by {name}, e.g.: {titles}")


def run_filter(input_path: str, output_path: str) -> int:
    if not require_dir(input_path):
        return 1

    # overwrite deletes the target first.
    if os.path.abspath(input_path) == os.path.abspath(output_path):
        log_error("input and output are the same folder")
        return 1

    spark = build_spark("vinf-wiki-filter", with_xml=False)

    try:
        ui_url = spark.sparkContext.uiWebUrl

        if ui_url is not None:
            log_info(f"spark UI: {ui_url}")

        articles = spark.read.parquet(input_path)

        # Cheap: parquet count reads only footers.
        total = articles.count()
        log_info(f"input articles: {total}")

        log_add(f"writing relevant articles to {output_path}")
        keep_relevant(add_relevance_flags(articles)).write.mode("overwrite").parquet(output_path)

        kept = spark.read.parquet(output_path)
        counts = summarize(kept)

        if counts.get("kept", 0) == 0:
            log_alert("no article was kept: the filter or the input is wrong")
            return 1

        _log_counts(counts, total)
        _log_samples(kept)
    finally:
        spark.stop()

    return 0