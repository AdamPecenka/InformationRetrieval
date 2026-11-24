# Stdlib only: imported inside the PyLucene container (no pyspark there).
import os

from constants.common import DATA_DIR
from constants.extractor import ATHLETE_COLUMNS

LUCENE_DIR: str = os.path.join(DATA_DIR, "lucene")
# Written on the host by lucene-export, read in the container.
LUCENE_DOCS_PATH: str = os.path.join(LUCENE_DIR, "docs.tsv")
LUCENE_INDEX_DIR: str = os.path.join(LUCENE_DIR, "index")

LUCENE_VM_ARGS: list[str] = ["-Djava.awt.headless=true"]

# docs.tsv: one row = one Lucene document = one athlete (both / olympedia_only) or one Wikipedia page (wiki_only).
# doc_id: athlete_id, or "w" + wiki_page_id for wiki_only. match_type: constants/join.py JOIN_MATCH_*.
LUCENE_KEY_COLUMNS: list[str] = ["doc_id", "match_type"]
LUCENE_WIKI_DOC_PREFIX: str = "w"

LUCENE_YEAR_COLUMNS: list[str] = ["born_year", "died_year"]

# Distinct values over the athlete's results rows. *_medals are lower-case "sport:medal" pairs,
# so "gold in swimming" != "gold in X + swam in Y".
LUCENE_RESULT_COLUMNS: list[str] = [
    "sports", "disciplines", "events", "games", "seasons", "result_years", "result_medals",
    "sport_medals", "discipline_medals",
]

# Best (lowest tier) Wikipedia page of the join, empty if none. wiki_only: the page itself.
LUCENE_WIKI_COLUMNS: list[str] = [
    "wiki_page_id", "wiki_tier", "wiki_title", "wiki_sport", "wiki_nationality", "wiki_lead", "wiki_body",
]

# height_cm, weight_kg, born_place, died_place are filled from Wikipedia where Olympedia has none.
# wiki_only rows: athlete_id and the results columns stay empty.
LUCENE_DOC_COLUMNS: list[str] = (
    LUCENE_KEY_COLUMNS + ATHLETE_COLUMNS + LUCENE_YEAR_COLUMNS + LUCENE_RESULT_COLUMNS + LUCENE_WIKI_COLUMNS
)

# Index schema. Values and queries both go through strip_accents.
# Only doc_id is an indexed key; athlete_id, match_type, full_name, sports, wiki_title are also stored for printing.

# A field fed by several columns gets each value once (compared accent- and case-insensitively, first kept).
# Title columns lose their disambiguation suffix first: "John Davis (swimmer)" -> "John Davis".
LUCENE_TITLE_COLUMNS: list[str] = ["wiki_title"]

LUCENE_NAME_FIELD: str = "name"
LUCENE_NAME_COLUMNS: list[str] = ["full_name", "used_name", "other_names", "original_name", "nickname", "wiki_title"]

# TextField + StandardAnalyzer. index field -> docs.tsv columns (Olympedia first, then Wikipedia).
LUCENE_PHRASE_FIELDS: dict[str, list[str]] = {
    "born_place": ["born_place"],
    "born_country": ["born_country"],
    "died_place": ["died_place"],
    "died_country": ["died_country"],
    "affiliations": ["affiliations"],
    "noc_names": ["noc_names"],
    "nationality_names": ["nationality_names", "wiki_nationality"],
    "roles": ["roles"],
    "other_participations": ["other_participations"],
    "sport": ["sports", "wiki_sport"],
    "discipline": ["disciplines"],
    "event": ["events"],
    "games": ["games"],
    "medal": ["result_medals"],
}

# TextField + EnglishAnalyzer (stemming, stop words).
LUCENE_PROSE_FIELDS: list[str] = [
    "biography", "post_career", "career_events", "list_mentions", "world_records", "personal_bests",
    "wiki_lead", "wiki_body",
]

# StringField, lower case, for filters.
LUCENE_KEYWORD_FIELDS: dict[str, str] = {
    "sex": "sex",
    "noc_codes": "noc_codes",
    "nationality_codes": "nationality_codes",
    "season": "seasons",
    "sport_medal": "sport_medals",
    "discipline_medal": "discipline_medals",
    "match_type": "match_type",
}

# IntPoint + StoredField.
LUCENE_INT_FIELDS: dict[str, str] = {
    "born_year": "born_year",
    "died_year": "died_year",
    "height_cm": "height_cm",
    "weight_kg": "weight_kg",
    "medals_gold": "medals_gold",
    "medals_silver": "medals_silver",
    "medals_bronze": "medals_bronze",
    "medals_total": "medals_total",
}
# IntPoint per value, not stored.
LUCENE_INT_LIST_FIELDS: dict[str, str] = {"result_year": "result_years"}

# Fields a bare query word hits, with boosts.
LUCENE_SEARCH_BOOSTS: dict[str, float] = {
    "name": 3.0,
    "sport": 1.5,
    "affiliations": 1.5,
    "discipline": 1.0,
    "event": 1.0,
    "medal": 1.0,
    "born_place": 1.0,
    "born_country": 1.0,
    "nationality_names": 1.0,
    "noc_names": 1.0,
    "roles": 0.5,
    "other_participations": 0.5,
    "world_records": 1.0,
    "post_career": 0.5,
    "career_events": 0.5,
    "biography": 0.5,
    "wiki_lead": 0.5,
    "wiki_body": 0.3,
}

# Lucene defaults (own index uses b = 0.3).
LUCENE_BM25_K1: float = 1.2
LUCENE_BM25_B: float = 0.75

LUCENE_PROGRESS_EVERY_DOCS: int = 20000

# Own index vs Lucene comparison.
LUCENE_COMPARISON_PATH: str = os.path.join(LUCENE_DIR, "comparison.tsv")
LUCENE_COMPARISON_RANKS_PATH: str = os.path.join(LUCENE_DIR, "comparison_ranks.tsv")
LUCENE_COMPARISON_REPEATS: int = 20
LUCENE_COMPARISON_COLUMNS: list[str] = [
    "case", "query_type", "truth", "old_found", "old_precision", "old_recall", "old_ms",
    "new_found", "new_precision", "new_recall", "new_ms",
]
LUCENE_COMPARISON_RANK_COLUMNS: list[str] = ["case", "athlete_id", "old_idf", "old_prob", "old_bm25", "new_bm25", "new_classic"]
