import os

from constants.common import DATA_DIR

# ---- dump ----
WIKI_DUMP_PATH: str = os.environ.get("VINF_WIKI_DUMP")
WIKI_DIR: str = os.path.join(DATA_DIR, "wiki")
WIKI_SLICE_PATH: str = os.path.join(WIKI_DIR, "slice.xml")
WIKI_PAGES_PATH: str = os.path.join(WIKI_DIR, "pages_parquet")
WIKI_SLICE_PAGES: int = 20000

# ---- relevance filter (stage 2) ----
WIKI_FULL_PAGES_PATH: str = os.path.join(WIKI_DIR, "pages_full_parquet")
WIKI_RELEVANT_PATH: str = os.path.join(WIKI_DIR, "pages_relevant_parquet")
WIKI_SAMPLES_DIR: str = os.path.join(WIKI_DIR, "samples")

# ---- attribute extraction (stage 3) ----
WIKI_PEOPLE_PATH: str = os.path.join(WIKI_DIR, "people_parquet")

# Only the article head goes to the UDF (infobox, medal table, lead); categories come from the whole text.
WIKI_HEAD_CHARS: int = 40000
WIKI_LEAD_MAX_CHARS: int = 1500
WIKI_SECTION_MAX_CHARS: int = 3000
WIKI_BODY_MAX_CHARS: int = 8000
WIKI_MAX_TEMPLATE_DEPTH: int = 10

# Templates replaced by their content instead of dropped.
WIKI_LIST_TEMPLATES: set[str] = {"hlist", "plainlist", "flatlist", "ubl", "unbulleted list", "bulleted list"}
WIKI_PASSTHROUGH_TEMPLATES: set[str] = {"nowrap", "nobr", "small", "big", "abbr"}
WIKI_CIRCA_TEMPLATES: set[str] = {"circa", "c.", "c", "ca", "ca."}
WIKI_CONVERT_TEMPLATES: set[str] = {"convert", "cvt"}
WIKI_LANG_TEMPLATES: set[str] = {"lang", "transl", "native name"}
WIKI_MEASURE_TEMPLATES: set[str] = {"height", "weight"}

WIKI_MONTHS: dict[str, int] = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# ---- measurements ----
WIKI_FEET_UNITS: set[str] = {"ft", "feet", "foot"}
WIKI_INCH_UNITS: set[str] = {"in", "inch", "inches"}
WIKI_STONE_UNITS: set[str] = {"st", "stone"}
WIKI_POUND_UNITS: set[str] = {"lb", "lbs", "pound", "pounds"}
# Plausible values; anything outside is a parse error.
WIKI_HEIGHT_RANGE_CM: tuple[int, int] = (100, 250)
WIKI_WEIGHT_RANGE_KG: tuple[int, int] = (30, 250)

WIKI_MEDAL_KINDS: set[str] = {"gold", "silver", "bronze"}
