"""Name normalisation for the join. Pure Python, no Spark."""
import unicodedata
from typing import Optional

import constants


def repair_mojibake(text: str) -> str:
    """UTF-8 bytes that were read as Windows-1252 ("PyrÃ©nÃ©es") back to the real text. Anything else is returned unchanged."""
    if constants.JOIN_MOJIBAKE_PATTERN.search(text) is None:
        return text

    try:
        return text.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def normalize_name(text: Optional[str]) -> Optional[str]:
    """lower case, no accents, only a-z0-9 separated by single spaces: "Hervé Gardye-de la Chapelle" -> "herve gardye de la chapelle"."""
    if text is None:
        return None

    repaired = repair_mojibake(text).lower()

    for letter, replacement in constants.JOIN_NAME_LETTER_MAP.items():
        repaired = repaired.replace(letter, replacement)

    decomposed = unicodedata.normalize("NFKD", repaired)
    without_accents = "".join(character for character in decomposed if not unicodedata.combining(character))
    normalized = constants.JOIN_NAME_NON_ALNUM_PATTERN.sub(" ", without_accents).strip()

    if normalized == "":
        return None

    return normalized


def was_repaired(text: Optional[str]) -> bool:
    return text is not None and repair_mojibake(text) != text