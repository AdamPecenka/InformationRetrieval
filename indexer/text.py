import unicodedata

from regexes.indexer import TOKEN_PATTERN


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def tokenize(text: str) -> list[str]:
    """Lower-case, strip accents, split into alphanumeric tokens. No stop words / stemming, idf handles frequent terms."""
    return TOKEN_PATTERN.findall(strip_accents(text).lower())