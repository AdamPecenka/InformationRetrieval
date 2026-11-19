import os
import sys

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import LongType, StringType, StructField, StructType

from common.log import log_add, log_info
from constants.common import ROOT_DIR, SPARK_DRIVER_MEMORY, SPARK_LOCAL_DIR, SPARK_XML_PACKAGE
from regexes.wiki import WIKI_BIO_REGEX
from wiki.inputs import require_file

# Explicit, inference would scan the whole dump. spark-xml: attributes are "_x", text next to attributes is "_VALUE".
PAGE_SCHEMA: StructType = StructType([
    StructField("title", StringType(), True),
    StructField("ns", LongType(), True),
    StructField("id", LongType(), True),
    StructField("redirect", StructType([
        StructField("_title", StringType(), True),
    ]), True),
    StructField("revision", StructType([
        StructField("id", LongType(), True),
        StructField("timestamp", StringType(), True),
        StructField("text", StructType([
            StructField("_VALUE", StringType(), True),
            StructField("_bytes", LongType(), True),
        ]), True),
    ]), True),
])


def build_spark(app_name: str = "vinf-wiki-parse", with_xml: bool = True) -> SparkSession:
    # Workers must use this venv's interpreter, not the first python on PATH.
    os.environ["PYSPARK_PYTHON"] = sys.executable
    os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

    # UDFs are pickled by module reference, workers must be able to import the project from ROOT_DIR.
    existing_path = os.environ.get("PYTHONPATH", "")

    if ROOT_DIR not in existing_path.split(os.pathsep):
        os.environ["PYTHONPATH"] = ROOT_DIR if existing_path == "" else ROOT_DIR + os.pathsep + existing_path

    builder = (
        SparkSession.builder
        .master("local[*]")
        .appName(app_name)
        .config("spark.driver.memory", SPARK_DRIVER_MEMORY)
    )

    # spark-xml only for the XML reader.
    if with_xml:
        builder = builder.config("spark.jars.packages", SPARK_XML_PACKAGE)

    if SPARK_LOCAL_DIR != "":
        builder = builder.config("spark.local.dir", SPARK_LOCAL_DIR)

    return builder.getOrCreate()


def read_pages(spark: SparkSession, path: str) -> DataFrame:
    return (
        spark.read.format("xml")
        .option("rowTag", "page")
        .schema(PAGE_SCHEMA)
        .load(path)
    )


def select_articles(pages: DataFrame, bio_only: bool) -> DataFrame:
    """Real articles only: main namespace, no redirects, with text."""
    articles = (
        pages
        .filter(F.col("ns") == 0)
        .filter(F.col("redirect").isNull())
        .select(
            F.col("id").alias("page_id"),
            F.col("title"),
            F.col("revision.timestamp").alias("revision_timestamp"),
            F.col("revision.text._VALUE").alias("wikitext"),
        )
        .filter(F.col("wikitext").isNotNull())
    )

    if bio_only:
        articles = articles.filter(F.col("wikitext").rlike(WIKI_BIO_REGEX))

    return articles


def run_parse(input_path: str, output_path: str, bio_only: bool) -> int:
    if not require_file(input_path):
        return 1

    spark = build_spark()

    try:
        ui_url = spark.sparkContext.uiWebUrl

        if ui_url is not None:
            log_info(f"spark UI: {ui_url}")

        pages = read_pages(spark, input_path)

        # 1 partition on a big input = not split, no parallelism.
        log_info(f"input is read in {pages.rdd.getNumPartitions()} partition(s)")

        articles = select_articles(pages, bio_only)

        log_add(f"writing parquet to {output_path}")
        articles.write.mode("overwrite").parquet(output_path)

        written = spark.read.parquet(output_path)
        log_info(f"articles written: {written.count()}")
        written.select("page_id", "title").show(10, truncate=False)
    finally:
        spark.stop()

    return 0