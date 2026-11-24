# Runs in the PyLucene container. Classic Lucene query syntax; bare words hit LUCENE_SEARCH_BOOSTS fields,
# numeric clauses (born_year:[1980 TO *], -height_cm:[200 TO *]) become IntPoint filters.
import os

import lucene  # noqa: F401  before any java / org.apache import
from java.lang import Float, Integer
from java.nio.file import Paths
from java.util import HashMap
from org.apache.lucene.document import Document, IntPoint
from org.apache.lucene.index import DirectoryReader, Term
from org.apache.lucene.queryparser.classic import MultiFieldQueryParser, QueryParser, QueryParserBase
from org.apache.lucene.search import BooleanClause, BooleanQuery, IndexSearcher, MatchAllDocsQuery, Query, TermQuery
from org.apache.lucene.search.similarities import BM25Similarity, ClassicSimilarity
from org.apache.lucene.store import FSDirectory

from common.log import log_error, log_info
from constants.join import JOIN_MATCH_WIKI_ONLY
from constants.lucene import LUCENE_SEARCH_BOOSTS, LUCENE_VM_ARGS
from indexer.lucene_analysis import fold, make_analyzer
from indexer.lucene_query import NumericClause, extract_numeric_clauses


def make_parser(require_all: bool) -> MultiFieldQueryParser:
    boosts = HashMap()

    for field, boost in LUCENE_SEARCH_BOOSTS.items():
        boosts.put(field, Float.valueOf(boost))

    parser = MultiFieldQueryParser(list(LUCENE_SEARCH_BOOSTS), make_analyzer(), boosts)

    if require_all:
        parser.setDefaultOperator(QueryParser.Operator.AND)

    return parser


def numeric_query(clause: NumericClause) -> Query:
    low = Integer.MIN_VALUE if clause.low is None else clause.low
    high = Integer.MAX_VALUE if clause.high is None else clause.high

    if low == high:
        return IntPoint.newExactQuery(clause.field, low)

    return IntPoint.newRangeQuery(clause.field, low, high)


def build_query(
    text: str, parser: MultiFieldQueryParser, sport_medals: list[str], discipline_medals: list[str],
) -> Query:
    """Text is MUST (scored); numeric clauses and medal pairs are FILTER (unscored)."""
    remaining, clauses = extract_numeric_clauses(text)
    builder = BooleanQuery.Builder()

    if remaining != "":
        # JCC: static MultiFieldQueryParser.parse overloads hide the instance method, call it via the base class.
        builder.add(QueryParserBase.parse(parser, fold(remaining)), BooleanClause.Occur.MUST)
    else:
        builder.add(MatchAllDocsQuery(), BooleanClause.Occur.MUST)

    for clause in clauses:
        occur = BooleanClause.Occur.MUST_NOT if clause.negated else BooleanClause.Occur.FILTER
        builder.add(numeric_query(clause), occur)

    for pair in sport_medals:
        builder.add(TermQuery(Term("sport_medal", fold(pair).lower())), BooleanClause.Occur.FILTER)

    for pair in discipline_medals:
        builder.add(TermQuery(Term("discipline_medal", fold(pair).lower())), BooleanClause.Occur.FILTER)

    return builder.build()


def describe_hit(document: Document) -> str:
    """Athletes: id, name, sports. wiki_only: page title (no athlete_id, no results)."""
    doc_id = document.get("doc_id") or document.get("athlete_id") or "?"
    name = document.get("full_name") or document.get("wiki_title") or "?"
    born = document.get("born_year") or "?"
    medals = document.get("medals_total") or "0"
    match_type = document.get("match_type") or "?"

    if match_type == JOIN_MATCH_WIKI_ONLY:
        details = f"wiki: {document.get('wiki_title')}"
    else:
        details = document.get("sports") or "no results"

    return f"{doc_id:>9}  {name}  (b. {born}, medals {medals}, {details}) [{match_type}]"


def run_lucene_search(
    text: str, top_k: int, require_all: bool, similarity: str, k1: float, b: float,
    sport_medals: list[str], discipline_medals: list[str], index_dir: str,
) -> int:
    if not os.path.isdir(index_dir):
        log_error(f"no index in {index_dir}, run: python main.py lucene-index")
        return 1

    lucene.initVM(vmargs=LUCENE_VM_ARGS)
    reader = DirectoryReader.open(FSDirectory.open(Paths.get(index_dir)))

    try:
        searcher = IndexSearcher(reader)

        if similarity == "classic":
            searcher.setSimilarity(ClassicSimilarity())
        else:
            searcher.setSimilarity(BM25Similarity(k1, b))

        try:
            query = build_query(text, make_parser(require_all), sport_medals, discipline_medals)
        except lucene.JavaError as error:
            log_error(f"cannot parse the query: {error}")
            return 1

        hits = searcher.search(query, top_k).scoreDocs
        stored = searcher.storedFields()
        log_info(f"query: {query}")
        log_info(f"{searcher.count(query)} matching documents, showing {len(hits)} ({similarity}, {'AND' if require_all else 'OR'})")

        for position, hit in enumerate(hits, start=1):
            print(f"{position:>3}. {hit.score:8.4f}  {describe_hit(stored.document(hit.doc))}")
    finally:
        reader.close()

    return 0