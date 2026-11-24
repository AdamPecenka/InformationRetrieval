"""Stage 4: join Olympedia athletes (athletes.tsv) with Wikipedia people (wiki-extract output).

Tiers, best first:
  0  exact id     page cites olympedia.org/athletes/<athlete_id>
  1  name + date  normalised name match and equal full birth date
  2  name + year  normalised name match and equal birth year
Name alone is not a tier (too ambiguous), only reported. Olympedia side is small -> always broadcast.
Full output: matched pairs + unmatched athletes + unmatched Olympic-flagged person pages (anti-joins + union,
a real full outer join over 2 M pages can't be broadcast).
"""
from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import StringType

from common.log import log_add, log_alert, log_error, log_info
from constants.join import (
    JOIN_BIRTH_YEAR_TOLERANCE,
    JOIN_HEIGHT_TOLERANCE_CM,
    JOIN_ID_YEAR_TOLERANCE,
    JOIN_MATCH_BOTH,
    JOIN_MATCH_OLYMPEDIA_ONLY,
    JOIN_MATCH_WIKI_ONLY,
    JOIN_WEIGHT_TOLERANCE_KG,
)
from regexes.join import JOIN_FULL_DATE_REGEX, JOIN_TITLE_SUFFIX_REGEX, JOIN_YEAR_REGEX
from wiki.audit import read_athletes
from wiki.dump import build_spark
from wiki.inputs import require_dir, require_file
from wiki.names import normalize_name, was_repaired
from wiki.relevance import OLYMPIC_FLAGS, any_of

_normalize_udf = F.udf(normalize_name, StringType())

# Carried into the output to compare both sides.
ATHLETE_COLUMNS: list[str] = [
    "athlete_id", "used_name", "full_name", "born_date", "born_place", "died_date",
    "nationality_names", "height_cm", "weight_kg", "medals_gold", "medals_silver", "medals_bronze",
]
WIKI_COLUMNS: list[str] = [
    "page_id", "title", "birth_date", "birth_place", "death_date", "death_place", "nationality",
    "sport", "height_cm", "weight_kg", "olympic_gold", "olympic_silver", "olympic_bronze",
    "olympic_games", "olympedia_id", "lead", "body",
]
TIER_LABELS: dict[int, str] = {0: "exact id", 1: "name + birth date", 2: "name + birth year"}
SAMPLE_ROWS: int = 12


def prepare_athletes(raw: DataFrame) -> DataFrame:
    """Athletes with a birth year and a full birth date taken from born_date."""
    missing = [column for column in ATHLETE_COLUMNS if column not in raw.columns]

    if len(missing) > 0:
        raise ValueError(f"athletes.tsv lacks columns: {missing}")

    born = F.col("born_date")

    return (
        raw.select(*ATHLETE_COLUMNS)
        .withColumn("born_year", F.when(born.rlike(JOIN_YEAR_REGEX), F.substring(born, 1, 4).cast("int")))
        .withColumn("born_full", F.when(born.rlike(JOIN_FULL_DATE_REGEX), born))
    )


def athlete_keys(athletes: DataFrame) -> DataFrame:
    """(athlete_id, name_key): the normalised used_name and full_name of every athlete."""
    used = athletes.select("athlete_id", _normalize_udf(F.col("used_name")).alias("name_key"))
    full = athletes.select("athlete_id", _normalize_udf(F.col("full_name")).alias("name_key"))

    return used.unionByName(full).filter(F.col("name_key").isNotNull()).distinct()


def wiki_keys(people: DataFrame) -> DataFrame:
    """One row per (page, name_key) from title, infobox name and birth name.
    Both infobox and category birth year are kept, they sometimes disagree."""
    title_base = F.regexp_replace(F.col("title"), JOIN_TITLE_SUFFIX_REGEX, "")
    keys = F.array_distinct(F.array(
        _normalize_udf(title_base),
        _normalize_udf(F.col("name")),
        _normalize_udf(F.col("birth_name")),
    ))

    return (
        people
        .select(
            "page_id",
            F.col("birth_year").alias("infobox_year"),
            F.col("category_birth_year").alias("category_year"),
            F.when(F.length(F.col("birth_date")) == 10, F.col("birth_date")).alias("wiki_full"),
            F.explode(keys).alias("name_key"),
        )
        .filter(F.col("name_key").isNotNull())
    )


def id_candidates(people: DataFrame, athletes: DataFrame) -> DataFrame:
    """Pages citing an athlete's id, with year_gap = min |wiki year - born_year| (null if a side lacks a year).

    status: exact | off_by_one (<= JOIN_ID_YEAR_TOLERANCE) | conflict (likely a coach's / relative's id) | unknown."""
    cited = (
        people
        .filter(F.col("olympedia_id").isNotNull())
        .select(
            "page_id", "title",
            F.col("olympedia_id").alias("athlete_id"),
            F.col("birth_year").alias("infobox_year"),
            F.col("category_birth_year").alias("category_year"),
        )
    )
    born = athletes.select("athlete_id", F.col("used_name").alias("athlete"), "born_year")
    joined = cited.join(F.broadcast(born), "athlete_id")
    gap = F.least(
        F.abs(F.col("infobox_year") - F.col("born_year")),
        F.abs(F.col("category_year") - F.col("born_year")),
    )
    with_gap = joined.withColumn("year_gap", gap)

    return with_gap.withColumn(
        "status",
        F.when(F.col("year_gap").isNull(), "unknown")
        .when(F.col("year_gap") == 0, "exact")
        .when(F.col("year_gap") <= JOIN_ID_YEAR_TOLERANCE, "off_by_one")
        .otherwise("conflict"),
    )


def id_pairs(candidates: DataFrame) -> DataFrame:
    """Tier 0: cited id, birth years not in conflict."""
    return (
        candidates
        .filter(F.col("status") != "conflict")
        .select("athlete_id", "page_id", F.lit(0).alias("tier"))
    )


def _tier_of_match(wiki_full: Column, infobox_year: Column, category_year: Column, born_full: Column, born_year: Column) -> Column:
    year_matches = born_year.isNotNull() & ((infobox_year == born_year) | (category_year == born_year))

    return (
        F.when(born_full.isNotNull() & (wiki_full == born_full), 1)
        .when(year_matches, 2)
    )


def name_candidates(keys_wiki: DataFrame, keys_athletes: DataFrame, athletes: DataFrame) -> DataFrame:
    """(athlete_id, page_id, tier) for equal name keys; tier is null for a name-only match."""
    born = athletes.select("athlete_id", "born_full", "born_year")
    joined = keys_wiki.join(F.broadcast(keys_athletes), "name_key").join(F.broadcast(born), "athlete_id")
    tier = _tier_of_match(F.col("wiki_full"), F.col("infobox_year"), F.col("category_year"), F.col("born_full"), F.col("born_year"))

    return (
        joined
        .select("athlete_id", "page_id", tier.alias("tier"))
        .groupBy("athlete_id", "page_id")
        .agg(F.min("tier").alias("tier"))
    )


def combine(by_id: DataFrame, by_name: DataFrame) -> DataFrame:
    """Every matched (athlete, page) once, with its best tier."""
    return (
        by_id.unionByName(by_name.filter(F.col("tier").isNotNull()))
        .groupBy("athlete_id", "page_id")
        .agg(F.min("tier").alias("tier"))
    )


def _count(frame: DataFrame) -> int:
    return frame.count()


def report_tiers(pairs: DataFrame) -> None:
    log_info("matched pairs per best tier: pairs / distinct athletes / distinct wikipedia pages")

    for tier, label in TIER_LABELS.items():
        part = pairs.filter(F.col("tier") == tier)
        pair_count = _count(part)
        athlete_count = _count(part.select("athlete_id").distinct())
        page_count = _count(part.select("page_id").distinct())
        log_info(f"  tier {tier} {label}: {pair_count} / {athlete_count} / {page_count}")

    for limit in range(len(TIER_LABELS)):
        cumulative = pairs.filter(F.col("tier") <= limit)
        pages = _count(cumulative.select("page_id").distinct())
        athletes = _count(cumulative.select("athlete_id").distinct())
        log_info(f"  tiers 0..{limit} together: {athletes} athletes, {pages} unique wikipedia pages")

    best = pairs.groupBy("athlete_id").agg(F.min("tier").alias("best"))
    at_best = pairs.join(best, "athlete_id").filter(F.col("tier") == F.col("best"))
    per_athlete = at_best.groupBy("athlete_id").count()
    ambiguous = _count(per_athlete.filter(F.col("count") > 1))
    per_page = pairs.groupBy("page_id").agg(F.countDistinct("athlete_id").alias("athletes"))
    shared = _count(per_page.filter(F.col("athletes") > 1))
    log_info(f"athletes with more than one page at their best tier: {ambiguous}")
    log_info(f"wikipedia pages matched to more than one athlete: {shared}")


def report_ambiguity_of_names(by_name: DataFrame, athletes: DataFrame) -> None:
    """Pages per athlete on name alone (shows why it is not a tier)."""
    total = _count(athletes.select("athlete_id").distinct())
    per_athlete = by_name.groupBy("athlete_id").count()
    with_any = _count(per_athlete)
    with_many = _count(per_athlete.filter(F.col("count") > 1))
    name_only = _count(by_name.filter(F.col("tier").isNull()))
    log_info(f"name only: {with_any} of {total} athletes share a name with some page, {with_many} with more than one page")
    log_info(f"name only: {name_only} (athlete, page) pairs have the same name but no equal birth date or year")


def report_id_consistency(candidates: DataFrame) -> DataFrame:
    """Logs exact-id candidates by status, returns the conflicts (excluded from the join)."""
    candidates.cache()
    counts = {row["status"]: row["count"] for row in candidates.groupBy("status").count().collect()}
    total = sum(counts.values())

    log_info(
        f"exact-id candidates: {total}; birth year equal {counts.get('exact', 0)}, "
        f"off by up to {JOIN_ID_YEAR_TOLERANCE} {counts.get('off_by_one', 0)}, "
        f"no year to compare {counts.get('unknown', 0)}, conflict {counts.get('conflict', 0)}"
    )

    conflicts = candidates.filter(F.col("status") == "conflict")

    if counts.get("conflict", 0) > 0:
        log_alert("id conflicts, set aside (the page cites another person's Olympedia id?):")
        conflicts.select("title", "athlete", "infobox_year", "category_year", "born_year", "athlete_id").orderBy(F.desc("year_gap")).show(SAMPLE_ROWS, truncate=False)

    return conflicts


def report_against_gold(by_id: DataFrame, by_name: DataFrame) -> None:
    """Precision / recall of the name tiers against tier 0 as gold (biased to pages citing Olympedia)."""
    gold_athletes = by_id.select("athlete_id").distinct()
    gold = by_id.select("athlete_id", "page_id").withColumn("gold", F.lit(1))
    name_pairs = (
        by_name.filter(F.col("tier").isNotNull())
        .join(gold_athletes, "athlete_id")
        .select("athlete_id", "page_id")
        .withColumn("found", F.lit(1))
    )

    found_total = _count(name_pairs)
    correct = _count(name_pairs.join(gold, ["athlete_id", "page_id"]))
    gold_total = _count(gold)
    recalled = _count(gold.join(name_pairs, ["athlete_id", "page_id"]))

    if found_total > 0:
        log_info(f"gold check, name tiers: precision {correct}/{found_total} = {100.0 * correct / found_total:.1f}%")

    if gold_total > 0:
        log_info(f"gold check, name tiers: recall {recalled}/{gold_total} = {100.0 * recalled / gold_total:.1f}%")


def athlete_side(athletes: DataFrame) -> DataFrame:
    return athletes.select(
        "athlete_id",
        F.col("used_name"), F.col("full_name"), F.col("born_date"), F.col("born_year"), F.col("born_place"), F.col("died_date"),
        F.col("nationality_names"),
        F.col("height_cm").cast("double").alias("olympedia_height_cm"),
        F.col("weight_kg").cast("double").alias("olympedia_weight_kg"),
        F.col("medals_gold"), F.col("medals_silver"), F.col("medals_bronze"),
    )


def wiki_side(people: DataFrame) -> DataFrame:
    return people.select(
        *[F.col(column) for column in WIKI_COLUMNS if column not in ("height_cm", "weight_kg", "olympedia_id")],
        F.col("birth_year").alias("infobox_year"),
        F.col("category_birth_year").alias("category_year"),
        F.col("height_cm").alias("wiki_height_cm"),
        F.col("weight_kg").alias("wiki_weight_kg"),
        F.col("olympedia_id").alias("wiki_olympedia_id"),
    )


def build_joined(pairs: DataFrame, athletes: DataFrame, people: DataFrame) -> DataFrame:
    joined = pairs.join(F.broadcast(athlete_side(athletes)), "athlete_id").join(wiki_side(people), "page_id")

    # Diffs are null when a side has no value.
    return (
        joined
        .withColumn("birth_year_diff", F.least(
            F.abs(F.col("infobox_year") - F.col("born_year")),
            F.abs(F.col("category_year") - F.col("born_year")),
        ))
        .withColumn("height_diff_cm", F.round(F.abs(F.col("olympedia_height_cm") - F.col("wiki_height_cm")), 1))
        .withColumn("weight_diff_kg", F.round(F.abs(F.col("olympedia_weight_kg") - F.col("wiki_weight_kg")), 1))
        .withColumn("birth_year_conflict", F.col("birth_year_diff") > JOIN_BIRTH_YEAR_TOLERANCE)
        .withColumn("height_conflict", F.col("height_diff_cm") > JOIN_HEIGHT_TOLERANCE_CM)
        .withColumn("weight_conflict", F.col("weight_diff_kg") > JOIN_WEIGHT_TOLERANCE_KG)
    )


def build_full(joined: DataFrame, athletes: DataFrame, people: DataFrame, conflicts: DataFrame) -> DataFrame:
    """joined rows (both) + unmatched athletes + unmatched Olympic-flagged pages, columns of the missing side null.
    id_conflict: the page cites an Olympedia id whose birth year doesn't fit (set aside by the tiers)."""
    matched_athletes = joined.select("athlete_id").distinct()
    matched_pages = joined.select("page_id").distinct()

    both = joined.withColumn("match_type", F.lit(JOIN_MATCH_BOTH))
    olympedia_only = (
        athlete_side(athletes)
        .join(F.broadcast(matched_athletes), "athlete_id", "left_anti")
        .withColumn("match_type", F.lit(JOIN_MATCH_OLYMPEDIA_ONLY))
    )
    wiki_only = (
        wiki_side(people.filter(any_of(OLYMPIC_FLAGS)))
        .join(F.broadcast(matched_pages), "page_id", "left_anti")
        .withColumn("match_type", F.lit(JOIN_MATCH_WIKI_ONLY))
    )
    full = (
        both
        .unionByName(olympedia_only, allowMissingColumns=True)
        .unionByName(wiki_only, allowMissingColumns=True)
    )
    conflict_pages = conflicts.select("page_id").distinct().withColumn("id_conflict", F.lit(True))

    return (
        full
        .join(F.broadcast(conflict_pages), "page_id", "left")
        .withColumn("id_conflict", F.coalesce(F.col("id_conflict"), F.lit(False)))
    )


def report_full(full: DataFrame, athlete_count: int) -> bool:
    """Counts per match_type; False when both + olympedia_only don't cover every athlete exactly once."""
    rows = full.groupBy("match_type").agg(
        F.count(F.lit(1)).alias("rows"),
        F.countDistinct("athlete_id").alias("athletes"),
        F.countDistinct("page_id").alias("pages"),
        F.sum(F.col("id_conflict").cast("int")).alias("id_conflicts"),
    ).collect()
    by_type = {row["match_type"]: row for row in rows}

    log_info("full join per match_type: rows / athletes / wikipedia pages / id-conflict pages")

    for match_type in (JOIN_MATCH_BOTH, JOIN_MATCH_OLYMPEDIA_ONLY, JOIN_MATCH_WIKI_ONLY):
        row = by_type.get(match_type)

        if row is None:
            log_info(f"  {match_type}: 0")
            continue

        log_info(f"  {match_type}: {row['rows']} / {row['athletes']} / {row['pages']} / {row['id_conflicts']}")

    covered = 0

    for match_type in (JOIN_MATCH_BOTH, JOIN_MATCH_OLYMPEDIA_ONLY):
        if match_type in by_type:
            covered += by_type[match_type]["athletes"]

    if covered != athlete_count:
        log_error(f"both + olympedia_only cover {covered} athletes, athletes.tsv has {athlete_count}")
        return False

    return True


def report_gaps_filled(joined: DataFrame) -> None:
    """Per distinct joined athlete: Olympedia fields that are empty but known on the wiki side."""
    athletes = _count(joined.select("athlete_id").distinct())
    checks: dict[str, Column] = {
        "height (olympedia empty, wikipedia known)": F.col("olympedia_height_cm").isNull() & F.col("wiki_height_cm").isNotNull(),
        "weight (olympedia empty, wikipedia known)": F.col("olympedia_weight_kg").isNull() & F.col("wiki_weight_kg").isNotNull(),
        "birth place (olympedia empty, wikipedia known)": F.col("born_place").isNull() & F.col("birth_place").isNotNull(),
        "death date (olympedia empty, wikipedia known)": F.col("died_date").isNull() & F.col("death_date").isNotNull(),
        "wikipedia lead text": F.col("lead").isNotNull(),
        "wikipedia body sections": F.col("body").isNotNull(),
        "wikipedia sport": F.col("sport").isNotNull(),
    }

    log_info(f"what wikipedia adds, per distinct joined athlete (of {athletes}):")

    for label, condition in checks.items():
        count = _count(joined.filter(condition).select("athlete_id").distinct())
        log_info(f"  {label}: {count}")


def report_source_conflicts(joined: DataFrame) -> None:
    """Pairs where the two sources disagree beyond the JOIN_*_TOLERANCE limits."""
    log_info("the two sources compared, per (athlete, page) pair with a value on both sides:")
    checks: list[tuple[str, str, str, str]] = [
        ("birth year", "birth_year_diff", "birth_year_conflict", f"more than {JOIN_BIRTH_YEAR_TOLERANCE} year apart"),
        ("height", "height_diff_cm", "height_conflict", f"more than {JOIN_HEIGHT_TOLERANCE_CM:g} cm apart"),
        ("weight", "weight_diff_kg", "weight_conflict", f"more than {JOIN_WEIGHT_TOLERANCE_KG:g} kg apart"),
    ]

    for label, diff_column, conflict_column, rule in checks:
        compared = _count(joined.filter(F.col(diff_column).isNotNull()))
        conflicting = _count(joined.filter(F.col(conflict_column)))
        log_info(f"  {label}: compared {compared}, {rule}: {conflicting} ({_percent(conflicting, compared)})")

    log_info("largest height disagreements:")
    (
        joined.filter(F.col("height_conflict"))
        .select("tier", "used_name", "title", "olympedia_height_cm", "wiki_height_cm", "height_diff_cm")
        .orderBy(F.desc("height_diff_cm"))
        .show(SAMPLE_ROWS, truncate=False)
    )


def _percent(part: int, whole: int) -> str:
    if whole == 0:
        return "n/a"

    return f"{100.0 * part / whole:.1f}%"


def run_join(people_path: str, athletes_path: str, output_path: str, full_output_path: str) -> int:
    if not require_dir(people_path) or not require_file(athletes_path):
        return 1

    if people_path in (output_path, full_output_path) or output_path == full_output_path:
        log_error("people, output and full output must be different paths, overwrite would delete an input")
        return 1

    spark = build_spark(app_name="vinf-wiki-join", with_xml=False)

    try:
        ui_url = spark.sparkContext.uiWebUrl

        if ui_url is not None:
            log_info(f"spark UI: {ui_url}")

        athletes = prepare_athletes(read_athletes(spark, athletes_path)).cache()
        people = spark.read.parquet(people_path)

        log_info(f"athletes: {_count(athletes)}, with a birth year: {_count(athletes.filter(F.col('born_year').isNotNull()))}, "
                 f"with a full birth date: {_count(athletes.filter(F.col('born_full').isNotNull()))}")
        _log_encoding(athletes)

        candidates = id_candidates(people, athletes)
        conflicts = report_id_consistency(candidates)
        by_id = id_pairs(candidates).cache()
        by_name = name_candidates(wiki_keys(people), athlete_keys(athletes), athletes).cache()
        pairs = combine(by_id, by_name).cache()

        report_tiers(pairs)
        report_ambiguity_of_names(by_name, athletes)
        report_against_gold(by_id, by_name)

        joined = build_joined(pairs, athletes, people)
        log_add(f"writing the joined pairs to {output_path}")
        joined.write.mode("overwrite").parquet(output_path)

        conflicts_path = output_path.rstrip("\\/") + "_conflicts"
        log_add(f"writing the id conflicts to {conflicts_path}")
        conflicts.write.mode("overwrite").parquet(conflicts_path)

        written = spark.read.parquet(output_path)
        report_gaps_filled(written)
        report_source_conflicts(written)
        written.select(
            "tier", "athlete_id", "used_name", "title", "born_date", "birth_date", "born_place", "birth_place",
            "olympedia_height_cm", "wiki_height_cm",
        ).orderBy("tier").show(SAMPLE_ROWS, truncate=False)

        full = build_full(written, athletes, people, spark.read.parquet(conflicts_path))
        log_add(f"writing the full join (both / olympedia_only / wiki_only) to {full_output_path}")
        full.write.mode("overwrite").parquet(full_output_path)

        if not report_full(spark.read.parquet(full_output_path), _count(athletes)):
            return 1
    finally:
        spark.stop()

    return 0


def _log_encoding(athletes: DataFrame) -> None:
    """Warns about mojibake in athletes.tsv (repaired for matching here, should be fixed at the source)."""
    repaired_udf = F.udf(was_repaired, "boolean")
    names = athletes.select(F.col("used_name"), F.col("full_name"))
    repaired = names.filter(repaired_udf(F.col("used_name")) | repaired_udf(F.col("full_name"))).count()

    if repaired > 0:
        log_alert(f"{repaired} athletes have mojibake in their name (UTF-8 read as Windows-1252); repaired for matching, fix the crawler output")