import os

from constants.common import DATA_DIR

# ---- join: Olympedia athletes <-> wikipedia people (stage 4) ----
WIKI_JOIN_PATH: str = os.path.join(DATA_DIR, "joined_parquet")

# Letters NFKD does not decompose.
JOIN_NAME_LETTER_MAP: dict[str, str] = {
    "ß": "ss", "æ": "ae", "œ": "oe", "ø": "o", "đ": "d", "ð": "d", "þ": "th", "ł": "l", "ı": "i",
}

# ---- tolerances ----
# An exact-id pair further apart than this is an id_conflict (page cites someone else's id).
JOIN_ID_YEAR_TOLERANCE: int = 1
# Beyond these the two sources are reported as disagreeing.
JOIN_BIRTH_YEAR_TOLERANCE: int = 1
JOIN_HEIGHT_TOLERANCE_CM: float = 3.0
JOIN_WEIGHT_TOLERANCE_KG: float = 5.0
