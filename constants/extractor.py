import os

from constants.common import DATA_DIR

# ---- output ----
EXTRACTED_DIR: str = os.path.join(DATA_DIR, "extracted")
ATHLETES_TSV_PATH: str = os.path.join(EXTRACTED_DIR, "athletes.tsv")
RESULTS_TSV_PATH: str = os.path.join(EXTRACTED_DIR, "results.tsv")
EXTRACT_PROGRESS_EVERY_PAGES: int = 1000
EXTRACT_MAX_PAGE_WARNINGS: int = 10

ATHLETE_COLUMNS: list[str] = [
    "athlete_id",
    "full_name",
    "given_names",
    "family_name",
    "used_name",
    "other_names",
    "original_name",
    "nickname",
    "sex",
    "roles",
    "born_date",
    "born_place",
    "born_country",
    "died_date",
    "died_place",
    "died_country",
    "height_cm",
    "weight_kg",
    "affiliations",
    "noc_codes",
    "noc_names",
    "nationality_codes",
    "nationality_names",
    "medals_gold",
    "medals_silver",
    "medals_bronze",
    "medals_total",
    "other_participations",
    "personal_bests",
    "world_records",
    "post_career",
    "career_events",
    "list_mentions",
    "biography",
]

RESULT_COLUMNS: list[str] = [
    "athlete_id",
    "games",
    "year",
    "season",
    "sport",
    "discipline",
    "event",
    "team",
    "position",
    "medal",
]

# ---- spark extraction (extract-spark) ----
OLYMPEDIA_ATHLETES_PARQUET_PATH: str = os.path.join(DATA_DIR, "extracted_parquet", "athletes")
OLYMPEDIA_RESULTS_PARQUET_PATH: str = os.path.join(DATA_DIR, "extracted_parquet", "results")
# ~124 MB of pages lands in few partitions, split so every core gets work.
OLYMPEDIA_SPARK_PARTITIONS: int = 64

# ---- page structure ----
# Lower-cased <h2> titles.
SECTION_BIOGRAPHICAL: str = "biographical information"
SECTION_BIOGRAPHY: str = "biography"
SECTION_RESULTS: str = "results"
SECTION_OTHER_PARTICIPATIONS: str = "other participations"
SECTION_LIST_MENTIONS: str = "list mentions"

# Row labels of the "Biographical information" table.
BIODATA_LABELS: frozenset[str] = frozenset(
    {
        "Roles",
        "Sex",
        "Full name",
        "Used name",
        "Other names",
        "Original name",
        "Nickname",
        "Born",
        "Died",
        "Measurements",
        "Affiliations",
        "NOC",
        "Nationality",
    }
)

MAX_COLSPAN: int = 12
BULLET: str = "•"

# ---- values ----
MEDAL_NAMES: tuple[str, ...] = ("Gold", "Silver", "Bronze")
MONTHS: dict[str, int] = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
