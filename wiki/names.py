"""Name normalisation for the join. Pure Python, no Spark."""
import unicodedata
from typing import Optional

from constants.join import JOIN_NAME_LETTER_MAP
from regexes.join import JOIN_MOJIBAKE_PATTERN, JOIN_NAME_NON_ALNUM_PATTERN


def repair_mojibake(text: str) -> str:
    """Undo UTF-8 read as Windows-1252 ("PyrÃ©nÃ©es"); other text unchanged."""
    if JOIN_MOJIBAKE_PATTERN.search(text) is None:
        return text

    try:
        return text.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def normalize_name(text: Optional[str]) -> Optional[str]:
    """Match key: "Hervé Gardye-de la Chapelle" -> "herve gardye de la chapelle"."""
    if text is None:
        return None

    repaired = repair_mojibake(text).lower()

    for letter, replacement in JOIN_NAME_LETTER_MAP.items():
        repaired = repaired.replace(letter, replacement)

    decomposed = unicodedata.normalize("NFKD", repaired)
    without_accents = "".join(character for character in decomposed if not unicodedata.combining(character))
    normalized = JOIN_NAME_NON_ALNUM_PATTERN.sub(" ", without_accents).strip()

    if normalized == "":
        return None

    return normalized


def was_repaired(text: Optional[str]) -> bool:
    return text is not None and repair_mojibake(text) != text