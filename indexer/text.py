import unicodedata

import constants


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def tokenize(text: str) -> list[str]:
    """Lower-case, strip accents, split into alphanumeric tokens.

    No stop word list and no stemming: the idf weight already pushes frequent
    words down (lecture: "Frekvencia termov a váženie").
    """
    return constants.TOKEN_PATTERN.findall(strip_accents(text).lower())