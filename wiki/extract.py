"""Stage 3: person attributes from the wiki-filter output (person-flagged pages only).

Parsing runs in a Python UDF (wiki/infobox.py) that gets only the head (WIKI_HEAD_CHARS) and the category names.
"""
from typing import Optional

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import (
    ArrayType,
    BooleanType,
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
)

from common.log import log_add, log_error, log_info
from constants.wiki import WIKI_HEAD_CHARS
from regexes.wiki import WIKI_CATEGORY_NAME_REGEX
from wiki.dump import build_spark
from wiki.infobox import FIELD_NAMES, extract_person
from wiki.inputs import require_dir

_STRING_FIELDS: set[str] = {
    "infobox_type", "name", "birth_name", "birth_date", "birth_place", "death_date", "death_place",
    "nationality", "sport", "category_country", "lead", "body",
}
_INTEGER_FIELDS: set[str] = {
    "birth_year", "death_year", "olympic_gold", "olympic_silver", "olympic_bronze",
    "category_birth_year", "category_death_year",
}
_DOUBLE_FIELDS: set[str] = {"height_cm", "weight_kg"}
_BOOLEAN_FIELDS: set[str] = {"birth_circa", "death_circa"}
_ARRAY_FIELDS: set[str] = {"olympic_games", "category_medal_kinds"}


def _field_type(name: str) -> StructField:
    if name in _STRING_FIELDS:
        return StructField(name, StringType(), True)

    if name in _INTEGER_FIELDS:
        return StructField(name, IntegerType(), True)

    if name in _DOUBLE_FIELDS:
        return StructField(name, DoubleType(), True)

    if name in _BOOLEAN_FIELDS:
        return StructField(name, BooleanType(), True)

    if name in _ARRAY_FIELDS:
        return StructField(name, ArrayType(StringType()), True)

    raise ValueError(f"no Spark type for field {name}")


ATTRIBUTE_SCHEMA: StructType = StructType([_field_type(name) for name in FIELD_NAMES])


def _extract_row(head: Optional[str], categories: Optional[list[str]]) -> tuple[object, ...]:
    attributes = extract_person(head, categories)
    return tuple(attributes[name] for name in FIELD_NAMES)


_extract_udf = F.udf(_extract_row, ATTRIBUTE_SCHEMA)


def select_people(relevant: DataFrame) -> DataFrame:
    """Same person signal that gates olympedia_id."""
    return relevant.filter(F.col("person_category") | F.col("person_infobox"))


def extract_attributes(people: DataFrame) -> DataFrame:
    head = F.substring(F.col("wikitext"), 1, WIKI_HEAD_CHARS)
    categories = F.expr(f"regexp_extract_all(wikitext, r'{WIKI_CATEGORY_NAME_REGEX}', 1)")

    with_attributes = people.withColumn("attributes", _extract_udf(head, categories))

    return with_attributes.select(
        "page_id",
        "title",
        "olympedia_id",
        "olympedia_id_count",
        F.col("olympic_title"),
        F.col("olympic_category"),
        F.col("olympic_medal"),
        F.col("olympedia_link"),
        *[F.col(f"attributes.{name}") for name in FIELD_NAMES],
    )


def _percent(part: int, whole: int) -> str:
    if whole == 0:
        return "n/a"

    return f"{100.0 * part / whole:.1f}%"


def _log_coverage(extracted: DataFrame) -> None:
    total = extracted.count()
    checks: dict[str, F.Column] = {
        "has infobox": F.col("infobox_type").isNotNull(),
        "lead text": F.col("lead").isNotNull(),
        "body (wanted sections found)": F.col("body").isNotNull(),
        "birth_date (infobox)": F.col("birth_date").isNotNull(),
        "birth_year (infobox or category)": F.coalesce(F.col("birth_year"), F.col("category_birth_year")).isNotNull(),
        "birth_place": F.col("birth_place").isNotNull(),
        "death_date": F.col("death_date").isNotNull(),
        "height_cm": F.col("height_cm").isNotNull(),
        "weight_kg": F.col("weight_kg").isNotNull(),
        "sport": F.col("sport").isNotNull(),
        "olympic games from categories": F.size(F.col("olympic_games")) > 0,
        "infobox says olympic medal": (F.col("olympic_gold") + F.col("olympic_silver") + F.col("olympic_bronze")) > 0,
        "olympedia_id": F.col("olympedia_id").isNotNull(),
    }
    aggregates = [F.sum(F.when(condition, 1).otherwise(0)).alias(label) for label, condition in checks.items()]
    row = extracted.agg(*aggregates).collect()[0]

    log_info(f"people extracted: {total}")

    for label in checks:
        count = int(row[label] or 0)
        log_info(f"  {label}: {count} ({_percent(count, total)})")

    disagreeing = (
        extracted
        .filter(F.col("birth_year").isNotNull() & F.col("category_birth_year").isNotNull())
        .filter(F.col("birth_year") != F.col("category_birth_year"))
        .count()
    )
    log_info(f"infobox birth year differs from the 'YYYY births' category: {disagreeing}")


def run_extract(input_path: str, output_path: str) -> int:
    if not require_dir(input_path):
        return 1

    if input_path == output_path:
        log_error("input and output are the same path, overwrite would delete the input")
        return 1

    spark = build_spark(app_name="vinf-wiki-extract", with_xml=False)

    try:
        ui_url = spark.sparkContext.uiWebUrl

        if ui_url is not None:
            log_info(f"spark UI: {ui_url}")

        relevant = spark.read.parquet(input_path)
        people = select_people(relevant)
        extracted = extract_attributes(people)

        log_add(f"writing parquet to {output_path}")
        extracted.write.mode("overwrite").parquet(output_path)

        written = spark.read.parquet(output_path)
        _log_coverage(written)

        written.select(
            "title", "birth_date", "death_date", "height_cm", "weight_kg", "olympic_gold", "olympic_silver", "olympic_bronze", "olympedia_id",
        ).show(15, truncate=False)
    finally:
        spark.stop()

    return 0