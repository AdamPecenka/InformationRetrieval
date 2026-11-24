# Runs in the PyLucene container (the own index is stdlib only, so it runs there too).
# Set cases -> precision / recall vs lucene_truth, rank cases -> rank of the known athlete.
# Athletes only: the own index and the truth know no wiki_only pages, so they are dropped from the truth rows
# and excluded from every Lucene query (MUST_NOT, no effect on scores; idf / avgdl still see the whole index).
import contextlib
import io
import os
import time
from typing import Callable, Optional

import lucene  # noqa: F401  before any java / org.apache import
from java.nio.file import Paths
from org.apache.lucene.index import DirectoryReader, Term
from org.apache.lucene.search import BooleanClause, BooleanQuery, IndexSearcher, Query, TermQuery
from org.apache.lucene.search.similarities import BM25Similarity, ClassicSimilarity
from org.apache.lucene.store import FSDirectory

from common.log import log_error, log_info
from common.tsv import format_row, iter_rows
from constants.indexer import INDEX_DICTIONARY_PATH, INDEX_DIR, INDEX_DOCS_PATH, INDEX_POSTINGS_PATH
from constants.join import JOIN_MATCH_WIKI_ONLY
from constants.lucene import (
    LUCENE_BM25_B,
    LUCENE_BM25_K1,
    LUCENE_COMPARISON_COLUMNS,
    LUCENE_COMPARISON_PATH,
    LUCENE_COMPARISON_RANK_COLUMNS,
    LUCENE_COMPARISON_RANKS_PATH,
    LUCENE_DOC_COLUMNS,
    LUCENE_VM_ARGS,
)
from indexer.lucene_builder import directory_size
from indexer.lucene_search import build_query, make_parser
from indexer.lucene_truth import RANK_CASES, SET_CASES, RankCase, SetCase
from indexer.ranking import RANKING_METHODS, documents_with_all_terms, rank
from indexer.storage import IndexReader


def format_number(value: Optional[float], digits: int = 2) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def time_ms(task: Callable[[], object], repeats: int) -> float:
    """Mean ms per call after one warm-up. stdout dropped (own index logs unknown terms)."""
    with contextlib.redirect_stdout(io.StringIO()):
        task()
        started = time.perf_counter()

        for _ in range(repeats):
            task()

        elapsed = time.perf_counter() - started

    return elapsed / repeats * 1000


def precision_recall(found: set[str], truth: set[str]) -> tuple[Optional[float], Optional[float]]:
    hits = len(found & truth)
    precision = hits / len(found) if len(found) > 0 else None
    recall = hits / len(truth) if len(truth) > 0 else None
    return precision, recall


def read_athlete_rows(docs_path: str) -> tuple[list[dict[str, str]], int]:
    """(non-wiki_only rows, all well-formed rows), streamed."""
    athletes: list[dict[str, str]] = []
    total = 0

    for fields in iter_rows(docs_path, LUCENE_DOC_COLUMNS):
        if fields is None:
            continue

        total += 1
        row = dict(zip(LUCENE_DOC_COLUMNS, fields))

        if row["match_type"] != JOIN_MATCH_WIKI_ONLY:
            athletes.append(row)

    return athletes, total


def athletes_only(query: Query) -> Query:
    builder = BooleanQuery.Builder()
    builder.add(query, BooleanClause.Occur.MUST)
    builder.add(TermQuery(Term("match_type", JOIN_MATCH_WIKI_ONLY)), BooleanClause.Occur.MUST_NOT)
    return builder.build()


def old_matches(reader: IndexReader, words: str) -> set[str]:
    return {reader.athlete_ids[doc_id] for doc_id in documents_with_all_terms(reader, words)}


def new_matches(searcher: IndexSearcher, case: SetCase, limit: int) -> list[str]:
    query = athletes_only(build_query(case.new_query, make_parser(True), [], case.new_discipline_medals))
    hits = searcher.search(query, limit).scoreDocs
    stored = searcher.storedFields()
    return [stored.document(hit.doc).get("athlete_id") for hit in hits]


def run_set_case(case: SetCase, rows: list[dict[str, str]], reader: IndexReader, searcher: IndexSearcher, repeats: int) -> list[str]:
    truth = {row["athlete_id"] for row in rows if case.truth(row)}
    fields: list[str] = [case.name, case.query_type, str(len(truth))]

    if case.old_query is None:
        fields.extend(["n/a", "-", "-", "-"])
    else:
        found = old_matches(reader, case.old_query)
        precision, recall = precision_recall(found, truth)
        milliseconds = time_ms(lambda: old_matches(reader, case.old_query or ""), repeats)
        fields.extend([str(len(found)), format_number(precision), format_number(recall), format_number(milliseconds, 3)])

    try:
        found_new = set(new_matches(searcher, case, len(rows)))
        precision, recall = precision_recall(found_new, truth)
        milliseconds = time_ms(lambda: new_matches(searcher, case, len(rows)), repeats)
        fields.extend([str(len(found_new)), format_number(precision), format_number(recall), format_number(milliseconds, 3)])
    except lucene.JavaError as error:
        log_error(f"{case.name}: the Lucene query failed: {error}")
        fields.extend(["error", "-", "-", "-"])

    return fields


def old_rank(reader: IndexReader, case: RankCase, method: str) -> Optional[int]:
    with contextlib.redirect_stdout(io.StringIO()):
        ranked = rank(reader, case.query, method, reader.n_docs, True)

    for position, (doc_id, _) in enumerate(ranked, start=1):
        if reader.athlete_ids[doc_id] == case.athlete_id:
            return position

    return None


def new_rank(searcher: IndexSearcher, case: RankCase, limit: int) -> Optional[int]:
    query = athletes_only(build_query(case.query, make_parser(True), [], []))
    stored = searcher.storedFields()

    for position, hit in enumerate(searcher.search(query, limit).scoreDocs, start=1):
        if stored.document(hit.doc).get("athlete_id") == case.athlete_id:
            return position

    return None


def run_rank_case(case: RankCase, reader: IndexReader, searcher: IndexSearcher, limit: int) -> list[str]:
    fields: list[str] = [case.name, case.athlete_id]
    fields.extend(format_number(old_rank(reader, case, method), 0) for method in RANKING_METHODS)

    searcher.setSimilarity(BM25Similarity(LUCENE_BM25_K1, LUCENE_BM25_B))
    fields.append(format_number(new_rank(searcher, case, limit), 0))
    searcher.setSimilarity(ClassicSimilarity())
    fields.append(format_number(new_rank(searcher, case, limit), 0))
    searcher.setSimilarity(BM25Similarity(LUCENE_BM25_K1, LUCENE_BM25_B))
    return fields


def write_tsv(path: str, header: list[str], table: list[list[str]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(format_row(header))

        for fields in table:
            handle.write(format_row(fields))


def run_lucene_compare(docs_path: str, index_dir: str, repeats: int) -> int:
    for path in (docs_path, INDEX_DICTIONARY_PATH, INDEX_POSTINGS_PATH, INDEX_DOCS_PATH):
        if not os.path.isfile(path):
            log_error(f"{path} not found (own index: python main.py index, Lucene: lucene-export then lucene-index)")
            return 1

    if not os.path.isdir(index_dir):
        log_error(f"no Lucene index in {index_dir}, run: python main.py lucene-index")
        return 1

    rows, document_count = read_athlete_rows(docs_path)

    lucene.initVM(vmargs=LUCENE_VM_ARGS)
    reader = IndexReader()
    lucene_reader = DirectoryReader.open(FSDirectory.open(Paths.get(index_dir)))

    try:
        searcher = IndexSearcher(lucene_reader)
        searcher.setSimilarity(BM25Similarity(LUCENE_BM25_K1, LUCENE_BM25_B))

        log_info(f"own index: {reader.n_docs} documents, {directory_size(INDEX_DIR) / 1_000_000:.1f} MB")
        log_info(f"Lucene index: {lucene_reader.numDocs()} documents, {directory_size(index_dir) / 1_000_000:.1f} MB")
        log_info(f"docs.tsv: {document_count} documents, {len(rows)} athletes compared. Latency = mean of {repeats} runs, parsing included")

        if reader.n_docs != len(rows) or lucene_reader.numDocs() != document_count:
            log_error("the indexes and docs.tsv differ in size, rebuild both from the same data")
            return 1

        comparison = [run_set_case(case, rows, reader, searcher, repeats) for case in SET_CASES]
        ranks = [run_rank_case(case, reader, searcher, len(rows)) for case in RANK_CASES]
    finally:
        lucene_reader.close()
        reader.close()

    print()
    print(f"{'query':<46} {'type':<24} {'truth':>5} | {'own: found':>10} {'P':>5} {'R':>5} {'ms':>8} | {'Lucene: found':>13} {'P':>5} {'R':>5} {'ms':>8}")

    for fields in comparison:
        print(f"{fields[0]:<46} {fields[1]:<24} {fields[2]:>5} | {fields[3]:>10} {fields[4]:>5} {fields[5]:>5} {fields[6]:>8} | "
              f"{fields[7]:>13} {fields[8]:>5} {fields[9]:>5} {fields[10]:>8}")

    print()
    print(f"{'rank of the right athlete':<28} {'id':>8} | {'own idf':>8} {'own prob':>9} {'own bm25':>9} | {'Lucene bm25':>12} {'Lucene classic':>15}")

    for fields in ranks:
        print(f"{fields[0]:<28} {fields[1]:>8} | {fields[2]:>8} {fields[3]:>9} {fields[4]:>9} | {fields[5]:>12} {fields[6]:>15}")

    write_tsv(LUCENE_COMPARISON_PATH, LUCENE_COMPARISON_COLUMNS, comparison)
    write_tsv(LUCENE_COMPARISON_RANKS_PATH, LUCENE_COMPARISON_RANK_COLUMNS, ranks)
    log_info(f"written: {LUCENE_COMPARISON_PATH}, {LUCENE_COMPARISON_RANKS_PATH}")
    return 0