import re

# `born_year:[1980 TO 1989]`, `medals_total:[3 TO *]`, `born_year:1985`, optional leading + / -.
LUCENE_NUMERIC_CLAUSE_PATTERN: re.Pattern[str] = re.compile(
    r"(?<!\w)(?P<sign>[+-]?)(?P<field>\w+):(?:\[(?P<low>\*|-?\d+)\s+TO\s+(?P<high>\*|-?\d+)\]|(?P<exact>-?\d+)(?![\w.]))"
)
