# docs.tsv value helpers, no Lucene import.
from typing import Optional

from constants.common import LIST_SEPARATOR


def split_values(text: str) -> list[str]:
    """Distinct non-empty values, order kept."""
    values: list[str] = []

    for part in text.split(LIST_SEPARATOR.strip()):
        value = part.strip()

        if value != "" and value not in values:
            values.append(value)

    return values


def to_int(text: str) -> Optional[int]:
    try:
        return int(text)
    except ValueError:
        return None