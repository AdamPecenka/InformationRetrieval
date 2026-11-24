# docs.tsv value helpers, no Lucene import.
from typing import Optional

from constants.common import LIST_SEPARATOR
from constants.lucene import LUCENE_TITLE_COLUMNS
from indexer.text import strip_accents
from regexes.join import JOIN_TITLE_SUFFIX_PATTERN


def split_values(text: str) -> list[str]:
    """Distinct non-empty values, order kept."""
    values: list[str] = []

    for part in text.split(LIST_SEPARATOR.strip()):
        value = part.strip()

        if value != "" and value not in values:
            values.append(value)

    return values


def strip_title_suffix(title: str) -> str:
    """"John Davis (swimmer)" -> "John Davis"."""
    return JOIN_TITLE_SUFFIX_PATTERN.sub("", title).strip()


def field_values(row: dict[str, str], columns: list[str]) -> list[str]:
    """Values of one index field fed by several columns, each once (accent- and case-insensitive, first kept)."""
    values: list[str] = []
    seen: set[str] = set()

    for column in columns:
        for value in split_values(row[column]):
            if column in LUCENE_TITLE_COLUMNS:
                value = strip_title_suffix(value)

            key = strip_accents(value).lower()

            if value == "" or key in seen:
                continue

            seen.add(key)
            values.append(value)

    return values


def to_int(text: str) -> Optional[int]:
    try:
        return int(text)
    except ValueError:
        return None
