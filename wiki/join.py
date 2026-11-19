"""Stage 4: join the Olympedia athletes (our crawl, athletes.tsv) with the Wikipedia people (wiki-extract output).

Why a join: Olympedia knows the sport results of an athlete, Wikipedia adds life details and free text
that Olympedia lacks for many athletes (birth place, height, weight, a longer biography). The two sources
share no key, so a pair of records is matched in tiers, most reliable first:

  tier 0  exact id    the Wikipedia article cites olympedia.org/athletes/<id> and <id> is the athlete_id
  tier 1  name + date a normalised name (title, infobox name or birth name vs used_name or full_name)
                      and the same full birth date
  tier 2  name + year the same, with only the birth year equal (the date is missing on one side)

A name alone is not a tier: "John Davis" matches dozens of unrelated people. It is only counted, to show
how ambiguous names are. The Olympedia side is small (thousands of rows), so every join against it is a
broadcast join: the big Wikipedia side is never shuffled.
"""
from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import StringType

import constants
from common.log import log_add, log_alert, log_error, log_info
from wiki.audit import read_athletes
from wiki.dump import build_spark
from wiki.inputs import require_dir, require_file
from wiki.names import normalize_name, was_repaired

_normalize_udf = F.udf(normalize_name, StringType())

# Olympedia columns that are carried into the output, so that both sides can be compared there.
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
        .withColumn("born_year", F.when(born.rlike(constants.JOIN_YEAR_REGEX), F.substring(born, 1, 4).cast("int")))
        .withColumn("born_full", F.when(born.rlike(constants.JOIN_FULL_DATE_REGEX), born))
    )


def athlete_keys(athletes: DataFrame) -> DataFrame:
    """(athlete_id, name_key): the normalised used_name and full_name of every athlete."""
    used = athletes.select("athlete_id", _normalize_udf(F.col("used_name")).alias("name_key"))
    full = athletes.select("athlete_id", _normalize_udf(F.col("full_name")).alias("name_key"))

    return used.unionByName(full).filter(F.col("name_key").isNotNull()).distinct()


def wiki_keys(people: DataFrame) -> DataFrame:
    """One row per (page, normalised name): the title without "(swimmer)", the infobox name and the birth name.
    The infobox and the "YYYY births" category sometimes disagree, so both years are kept."""
    title_base = F.regexp_replace(F.col("title"), constants.JOIN_TITLE_SUFFIX_REGEX, "")
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
    """Every page that cites an athlete's Olympedia id, with the birth-year gap between the two sources.

    year_gap is the smaller distance between the athlete's birth year and the infobox or the category year (null when a
    side has no year). status: exact (gap 0), off_by_one (gap within JOIN_ID_YEAR_TOLERANCE), conflict (further apart,
    the page most likely cites a coach's or relative's id), unknown (no year to compare)."""
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
        .when(F.col("year_gap") <= constants.JOIN_ID_YEAR_TOLERANCE, "off_by_one")
        .otherwise("conflict"),
    )


def id_pairs(candidates: DataFrame) -> DataFrame:
    """Tier 0: the cited id is the athlete's and the birth years do not contradict."""
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
    """(athlete_id, page_id, tier) for every page whose name key equals an athlete name key. tier is null
    for a name-only match (same name, but no equal birth date or year)."""
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
    """Why a name alone is not enough: pages per athlete when only the name is compared."""
    total = _count(athletes.select("athlete_id").distinct())
    per_athlete = by_name.groupBy("athlete_id").count()
    with_any = _count(per_athlete)
    with_many = _count(per_athlete.filter(F.col("count") > 1))
    name_only = _count(by_name.filter(F.col("tier").isNull()))
    log_info(f"name only: {with_any} of {total} athletes share a name with some page, {with_many} with more than one page")
    log_info(f"name only: {name_only} (athlete, page) pairs have the same name but no equal birth date or year")


def report_id_consistency(candidates: DataFrame) -> DataFrame:
    """Exact-id candidates by status. Returns the conflicts, which are kept apart from the join."""
    candidates.cache()
    counts = {row["status"]: row["count"] for row in candidates.groupBy("status").count().collect()}
    total = sum(counts.values())

    log_info(
        f"exact-id candidates: {total}; birth year equal {counts.get('exact', 0)}, "
        f"off by up to {constants.JOIN_ID_YEAR_TOLERANCE} {counts.get('off_by_one', 0)}, "
        f"no year to compare {counts.get('unknown', 0)}, conflict {counts.get('conflict', 0)}"
    )

    conflicts = candidates.filter(F.col("status") == "conflict")

    if counts.get("conflict", 0) > 0:
        log_alert("id conflicts, set aside (the page cites another person's Olympedia id?):")
        conflicts.select("title", "athlete", "infobox_year", "category_year", "born_year", "athlete_id").orderBy(F.desc("year_gap")).show(SAMPLE_ROWS, truncate=False)

    return conflicts


def report_against_gold(by_id: DataFrame, by_name: DataFrame) -> None:
    """The exact-id pairs are a gold standard for the name tiers (biased toward athletes whose page cites Olympedia).
    Precision: of the name + year pairs for those athletes, how many are the gold page. Recall: how many gold pairs the name tiers find."""
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


def build_joined(pairs: DataFrame, athletes: DataFrame, people: DataFrame) -> DataFrame:
    left = athletes.select(
        "athlete_id",
        F.col("used_name"), F.col("full_name"), F.col("born_date"), F.col("born_year"), F.col("born_place"), F.col("died_date"),
        F.col("nationality_names"),
        F.col("height_cm").cast("double").alias("olympedia_height_cm"),
        F.col("weight_kg").cast("double").alias("olympedia_weight_kg"),
        F.col("medals_gold"), F.col("medals_silver"), F.col("medals_bronze"),
    )
    right = people.select(
        *[F.col(column) for column in WIKI_COLUMNS if column not in ("height_cm", "weight_kg", "olympedia_id")],
        F.col("birth_year").alias("infobox_year"),
        F.col("category_birth_year").alias("category_year"),
        F.col("height_cm").alias("wiki_height_cm"),
        F.col("weight_kg").alias("wiki_weight_kg"),
        F.col("olympedia_id").alias("wiki_olympedia_id"),
    )
    joined = pairs.join(F.broadcast(left), "athlete_id").join(right, "page_id")

    # How far the two sources are apart. Null when one side has no value.
    return (
        joined
        .withColumn("birth_year_diff", F.least(
            F.abs(F.col("infobox_year") - F.col("born_year")),
            F.abs(F.col("category_year") - F.col("born_year")),
        ))
        .withColumn("height_diff_cm", F.round(F.abs(F.col("olympedia_height_cm") - F.col("wiki_height_cm")), 1))
        .withColumn("weight_diff_kg", F.round(F.abs(F.col("olympedia_weight_kg") - F.col("wiki_weight_kg")), 1))
        .withColumn("birth_year_conflict", F.col("birth_year_diff") > constants.JOIN_BIRTH_YEAR_TOLERANCE)
        .withColumn("height_conflict", F.col("height_diff_cm") > constants.JOIN_HEIGHT_TOLERANCE_CM)
        .withColumn("weight_conflict", F.col("weight_diff_kg") > constants.JOIN_WEIGHT_TOLERANCE_KG)
    )


def report_gaps_filled(joined: DataFrame) -> None:
    """What Wikipedia adds: Olympedia fields that are empty for a joined athlete but known on the wiki side.
    Counted per distinct athlete over the pairs of tiers 0..2."""
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
    """Where Olympedia and Wikipedia state different values for the same person (pairs of tiers 0..2)."""
    log_info("the two sources compared, per (athlete, page) pair with a value on both sides:")
    checks: list[tuple[str, str, str, str]] = [
        ("birth year", "birth_year_diff", "birth_year_conflict", f"more than {constants.JOIN_BIRTH_YEAR_TOLERANCE} year apart"),
        ("height", "height_diff_cm", "height_conflict", f"more than {constants.JOIN_HEIGHT_TOLERANCE_CM:g} cm apart"),
        ("weight", "weight_diff_kg", "weight_conflict", f"more than {constants.JOIN_WEIGHT_TOLERANCE_KG:g} kg apart"),
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


def run_join(people_path: str, athletes_path: str, output_path: str) -> int:
    if not require_dir(people_path) or not require_file(athletes_path):
        return 1

    if people_path == output_path:
        log_error("people and output are the same path, overwrite would delete the input")
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
    finally:
        spark.stop()

    return 0


def _log_encoding(athletes: DataFrame) -> None:
    """Names that had to be repaired mean athletes.tsv holds mojibake; the join repairs them, the source should be fixed."""
    repaired_udf = F.udf(was_repaired, "boolean")
    names = athletes.select(F.col("used_name"), F.col("full_name"))
    repaired = names.filter(repaired_udf(F.col("used_name")) | repaired_udf(F.col("full_name"))).count()

    if repaired > 0:
        log_alert(f"{repaired} athletes have mojibake in their name (UTF-8 read as Windows-1252); repaired for matching, fix the crawler output")