"""Stage 2: keep the Wikipedia articles the Olympedia join and the later extraction can use.

An article is kept when ANY of six independent signals fires. The signals are stored as boolean
columns in the output, so later stages can see why a page was kept and the rules can be audited.

    person_category   a births / deaths / "Living people" category
    person_infobox    a birth date field or birth date template (fallback for pages without such a category)
    olympic_title     the title mentions the Olympics ("Germany at the 1976 Summer Olympics")
    olympic_category  an Olympic category ("Olympic medalists in swimming")
    olympic_medal     a medal template that mentions the Olympics
    olympedia_link    a link to Olympedia (URL, reference or {{Olympedia}} template)

The output also gets olympedia_id_count (distinct athlete ids cited on the page) and olympedia_id (the id, only
for a person page that cites exactly one), for an exact join.
"""

import os

from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F

import constants
from common.log import log_add, log_alert, log_error, log_info
from wiki.dump import build_spark
from wiki.inputs import require_dir

# (flag column, column the regex is applied to, regex). Cheapest first: the title check touches a few bytes,
# the others scan the whole text.
FLAG_RULES: list[tuple[str, str, str]] = [
    ("olympic_title", "title", constants.WIKI_OLYMPIC_TITLE_REGEX),
    ("person_category", "wikitext", constants.WIKI_PERSON_CATEGORY_REGEX),
    ("olympic_category", "wikitext", constants.WIKI_OLYMPIC_CATEGORY_REGEX),
    ("person_infobox", "wikitext", constants.WIKI_PERSON_INFOBOX_REGEX),
    ("olympic_medal", "wikitext", constants.WIKI_OLYMPIC_MEDAL_REGEX),
    ("olympedia_link", "wikitext", constants.WIKI_OLYMPEDIA_LINK_REGEX),
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
    # F.regexp_extract_all only exists from PySpark 3.5, the SQL function from Spark 3.1.
    # r'...' is a raw SQL string literal, so the backslashes reach the Java regex untouched.
    return F.expr(f"regexp_extract_all(wikitext, r'{pattern}', 1)")


def _add_olympedia_id(flagged: DataFrame) -> DataFrame:
    """olympedia_id_count: distinct athlete ids cited on the page (null without an Olympedia link).

    olympedia_id: the id, but only for a person page that cites exactly one. A date page or a list cites many
    athletes, and giving it the first one would join the page to the wrong person.
    """
    all_ids = F.array_distinct(F.concat(
        _extract_all(constants.WIKI_OLYMPEDIA_URL_ID_REGEX),
        _extract_all(constants.WIKI_OLYMPEDIA_TEMPLATE_ID_REGEX),
    ))
    is_person = F.col("person_category") | F.col("person_infobox")

    return (
        flagged
        .withColumn("olympedia_id_count", F.when(F.col("olympedia_link"), F.size(all_ids)))
        .withColumn("olympedia_id", F.when(is_person & (F.col("olympedia_id_count") == 1), all_ids[0]))
    )


def _any_of(names: list[str]) -> Column:
    condition = F.col(names[0])

    for name in names[1:]:
        condition = condition | F.col(name)

    return condition


def keep_relevant(flagged: DataFrame) -> DataFrame:
    return flagged.filter(_any_of(FLAG_COLUMNS))


def summarize(kept: DataFrame) -> dict[str, int]:
    """One pass over the flag columns of the kept articles.

    For every flag: how many pages it fires on, and how many are kept ONLY because of it.
    """
    person = _any_of(PERSON_FLAGS)
    olympic = _any_of(OLYMPIC_FLAGS)

    aggregations: list[Column] = [F.count(F.lit(1)).alias("kept")]

    for name in FLAG_COLUMNS:
        others = [other for other in FLAG_COLUMNS if other != name]

        aggregations.append(F.sum(F.col(name).cast("int")).alias(name))
        aggregations.append(F.sum((F.col(name) & ~_any_of(others)).cast("int")).alias(f"only_{name}"))

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
    person = _any_of(PERSON_FLAGS)
    olympic = _any_of(OLYMPIC_FLAGS)

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

    # Shows what each rule catches that no other rule does, to judge whether the rule is worth keeping.
    for name in FLAG_COLUMNS:
        others = [other for other in FLAG_COLUMNS if other != name]
        only_this = kept.filter(F.col(name) & ~_any_of(others)).select("title").limit(SAMPLE_PER_FLAG)
        titles = [row["title"] for row in only_this.collect()]

        if len(titles) > 0:
            log_info(f"  kept only by {name}, e.g.: {titles}")


def run_filter(input_path: str, output_path: str) -> int:
    if not require_dir(input_path):
        return 1

    # mode("overwrite") deletes the target first, which would delete the input if they were the same folder.
    if os.path.abspath(input_path) == os.path.abspath(output_path):
        log_error("input and output are the same folder")
        return 1

    spark = build_spark("vinf-wiki-filter", with_xml=False)

    try:
        ui_url = spark.sparkContext.uiWebUrl

        if ui_url is not None:
            log_info(f"spark UI: {ui_url}")

        articles = spark.read.parquet(input_path)

        # A parquet row count comes from the file footers, no text is read.
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