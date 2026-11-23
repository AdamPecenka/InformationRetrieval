# Comparison test cases. Truth is computed from docs.tsv, independent of both indexes.
# Uses the own index's tokenizer so a word means the same in the truth and the old index.
from dataclasses import dataclass
from typing import Callable, Optional

from constants.lucene import LUCENE_NAME_COLUMNS
from indexer.lucene_values import split_values, to_int
from indexer.text import tokenize

Row = dict[str, str]


@dataclass(frozen=True)
class SetCase:
    """Judged by precision / recall."""
    name: str
    query_type: str
    old_query: Optional[str]          # own index AND words, None = not expressible
    new_query: str
    new_discipline_medals: list[str]
    truth: Callable[[Row], bool]


@dataclass(frozen=True)
class RankCase:
    """Judged by the rank of athlete_id."""
    name: str
    query: str
    athlete_id: str


def has_token(row: Row, column: str, token: str) -> bool:
    return token in tokenize(row[column])


def has_phrase(row: Row, column: str, phrase: list[str]) -> bool:
    """Adjacent tokens within one list value."""
    for value in split_values(row[column]):
        tokens = tokenize(value)

        for start in range(len(tokens) - len(phrase) + 1):
            if tokens[start:start + len(phrase)] == phrase:
                return True

    return False


def name_tokens(row: Row) -> list[str]:
    tokens: list[str] = []

    for column in LUCENE_NAME_COLUMNS:
        tokens.extend(tokenize(row[column]))

    return tokens


def int_at_least(row: Row, column: str, minimum: int) -> bool:
    number = to_int(row[column])
    return number is not None and number >= minimum


def int_between(row: Row, column: str, low: int, high: int) -> bool:
    number = to_int(row[column])
    return number is not None and low <= number <= high


def within_one_edit(a: str, b: str) -> bool:
    """Damerau-Levenshtein <= 1, same as Lucene term~1."""
    if a == b:
        return True

    if abs(len(a) - len(b)) > 1:
        return False

    if len(a) == len(b):
        differences = [index for index in range(len(a)) if a[index] != b[index]]

        if len(differences) == 1:
            return True

        return (
            len(differences) == 2
            and differences[1] == differences[0] + 1
            and a[differences[0]] == b[differences[1]]
            and a[differences[1]] == b[differences[0]]
        )

    shorter, longer = (a, b) if len(a) < len(b) else (b, a)
    return any(longer[:index] + longer[index + 1:] == shorter for index in range(len(longer)))


SET_CASES: list[SetCase] = [
    SetCase(
        "born in Tbilisi, at least 1 medal", "term + range", "tbilisi",
        "born_place:tbilisi medals_total:[1 TO *]", [],
        lambda row: has_token(row, "born_place", "tbilisi") and int_at_least(row, "medals_total", 1),
    ),
    SetCase(
        "women born in Australia with swimming gold", "boolean + exact filters", "swimming gold aus",
        "sex:female born_country:aus", ["swimming:gold"],
        lambda row: row["sex"].lower() == "female" and row["born_country"].upper() == "AUS"
        and "swimming:gold" in split_values(row["discipline_medals"]),
    ),
    SetCase(
        "member of Dynamo Moskva", "phrase", "dynamo moskva",
        'affiliations:"dynamo moskva"', [],
        lambda row: has_phrase(row, "affiliations", ["dynamo", "moskva"]),
    ),
    SetCase(
        "NOC URS and Georgian nationality", "boolean on exact fields", "urs georgia",
        "noc_codes:urs nationality_names:georgia", [],
        lambda row: "urs" in [value.lower() for value in split_values(row["noc_codes"])]
        and has_token(row, "nationality_names", "georgia"),
    ),
    SetCase(
        "born 1980-1989 with at least 3 medals", "range", None,
        "born_year:[1980 TO 1989] medals_total:[3 TO *]", [],
        lambda row: int_between(row, "born_year", 1980, 1989) and int_at_least(row, "medals_total", 3),
    ),
    SetCase(
        "basketball players, at least 200 cm", "range + term", None,
        "discipline:basketball height_cm:[200 TO *]", [],
        lambda row: has_token(row, "disciplines", "basketball") and int_at_least(row, "height_cm", 200),
    ),
    SetCase(
        "gymnasts who were not in Dynamo Moskva", "boolean NOT + phrase", None,
        'sport:gymnastics NOT affiliations:"dynamo moskva"', [],
        lambda row: has_token(row, "sports", "gymnastics") and not has_phrase(row, "affiliations", ["dynamo", "moskva"]),
    ),
    SetCase(
        "name misspelled: phelp", "fuzzy (edit distance 1)", "phelp",
        "name:phelp~1", [],
        lambda row: any(within_one_edit(token, "phelp") for token in name_tokens(row)),
    ),
    SetCase(
        "name starts with phel", "prefix", "phel",
        "name:phel*", [],
        lambda row: any(token.startswith("phel") for token in name_tokens(row)),
    ),
]

RANK_CASES: list[RankCase] = [
    RankCase("michael phelps", "michael phelps", "93860"),
    RankCase("dawn fraser", "dawn fraser", "45044"),
    RankCase("mark spitz", "mark spitz", "51572"),
]