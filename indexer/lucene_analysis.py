import lucene  # noqa: F401  before any java / org.apache import
from java.util import HashMap
from org.apache.lucene.analysis.en import EnglishAnalyzer
from org.apache.lucene.analysis.miscellaneous import PerFieldAnalyzerWrapper
from org.apache.lucene.analysis.standard import StandardAnalyzer

from constants.lucene import LUCENE_PROSE_FIELDS
from indexer.text import strip_accents


def fold(text: str) -> str:
    return strip_accents(text)


def make_analyzer() -> PerFieldAnalyzerWrapper:
    per_field = HashMap()
    english = EnglishAnalyzer()

    for field in LUCENE_PROSE_FIELDS:
        per_field.put(field, english)

    return PerFieldAnalyzerWrapper(StandardAnalyzer(), per_field)