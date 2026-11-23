# Classic QueryParser can't do IntPoint ranges: numeric clauses are cut out here, the rest goes to the parser.
import re
from dataclasses import dataclass
from typing import Optional

from constants.lucene import LUCENE_INT_FIELDS, LUCENE_INT_LIST_FIELDS
from regexes.lucene import LUCENE_NUMERIC_CLAUSE_PATTERN

NUMERIC_FIELDS: frozenset[str] = frozenset(LUCENE_INT_FIELDS) | frozenset(LUCENE_INT_LIST_FIELDS)


@dataclass(frozen=True)
class NumericClause:
    field: str
    low: Optional[int]   # None = open end
    high: Optional[int]
    negated: bool        # leading "-"


def extract_numeric_clauses(text: str) -> tuple[str, list[NumericClause]]:
    """-> (rest of the text, clauses). Non-numeric fields stay in the text."""
    clauses: list[NumericClause] = []

    def take(match: re.Match[str]) -> str:
        field = match.group("field")

        if field not in NUMERIC_FIELDS:
            return match.group(0)

        if match.group("exact") is not None:
            low: Optional[int] = int(match.group("exact"))
            high: Optional[int] = low
        else:
            low = None if match.group("low") == "*" else int(match.group("low"))
            high = None if match.group("high") == "*" else int(match.group("high"))

        clauses.append(NumericClause(field, low, high, match.group("sign") == "-"))
        return " "

    remaining = LUCENE_NUMERIC_CLAUSE_PATTERN.sub(take, text)
    return " ".join(remaining.split()), clauses