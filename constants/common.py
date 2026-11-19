import os

# ---- paths ----
ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR: str = os.environ.get("VINF_DATA_DIR", os.path.join(ROOT_DIR, "data"))
# Written by the crawler, read by the extractor.
RAW_ATHLETES_DIR: str = os.path.join(DATA_DIR, "raw", "athletes")

# ---- site ----
BASE_URL: str = os.environ.get("VINF_BASE_URL", "https://www.olympedia.org").rstrip("/")

# ---- TSV ----
LIST_SEPARATOR: str = " | "

# ---- spark ----
SPARK_XML_PACKAGE: str = "com.databricks:spark-xml_2.12:0.18.0"
SPARK_DRIVER_MEMORY: str = os.environ.get("VINF_SPARK_DRIVER_MEMORY", "4g")
SPARK_LOCAL_DIR: str = os.environ.get("VINF_SPARK_TMP", "")
