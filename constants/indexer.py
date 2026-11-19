import os

from constants.common import DATA_DIR

# ---- paths ----
INDEX_DIR: str = os.path.join(DATA_DIR, "index")
INDEX_DICTIONARY_PATH: str = os.path.join(INDEX_DIR, "dictionary.tsv")
INDEX_POSTINGS_PATH: str = os.path.join(INDEX_DIR, "postings.tsv")
INDEX_DOCS_PATH: str = os.path.join(INDEX_DIR, "docs.tsv")
INDEX_BLOCKS_DIR: str = os.path.join(INDEX_DIR, "blocks")

# SPIMI: flush a block after this many postings (stand-in for "memory full").
INDEX_BLOCK_MAX_POSTINGS: int = 2_000_000
INDEX_PROGRESS_EVERY_DOCS: int = 5000

# ---- TSV layouts ----
DICTIONARY_COLUMNS: list[str] = ["term", "df", "offset"]
DOC_COLUMNS: list[str] = ["doc_id", "athlete_id", "full_name", "length", "norm"]

# ---- BM25 ----
# Lecture defaults: k1 in <1.2; 2>, b = 0.75. b is lowered to soften the length penalty.
BM25_K1: float = 1.2
BM25_B: float = 0.3

# ---- document text ----
# athletes.tsv columns that make up a document (one athlete = one document).
INDEX_TEXT_COLUMNS: list[str] = [
    "full_name",
    "used_name",
    "other_names",
    "original_name",
    "nickname",
    "roles",
    "born_place",
    "born_country",
    "died_place",
    "died_country",
    "affiliations",
    "noc_codes",
    "noc_names",
    "nationality_names",
    "other_participations",
    "personal_bests",
    "post_career",
    "career_events",
    "list_mentions",
    "biography",
]

# results.tsv columns appended to the athlete's document (joined on athlete_id).
INDEX_RESULT_COLUMNS: list[str] = ["year", "season", "sport", "discipline", "event", "medal"]
