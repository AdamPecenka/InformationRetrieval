import heapq
import math
from collections import Counter
from typing import Callable, Optional

from common.log import log_info
from constants.indexer import BM25_B, BM25_K1
from indexer.storage import IndexReader
from indexer.text import tokenize

# tf-idf:  Score(q,d) = sum_t tf(t,q) * idf(t) * (1 + log10 tf(t,d)) / ||d||   (||d|| from docs.tsv)
# bm25:    Score(q,d) = sum_t idf(t) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * |d| / avg|d|)), idf clamped at 0


def tf_weight(tf: int) -> float:
    """Logarithmic scaling: 1 + log10(tf) for tf > 0, else 0."""
    if tf <= 0:
        return 0.0

    return 1.0 + math.log10(tf)


def idf_classic(n_docs: int, df: int) -> float:
    """idf = log10(N / df)"""
    return math.log10(n_docs / df)


def idf_probabilistic(n_docs: int, df: int) -> float:
    """probabilistic idf = max(0, log10((N - df) / df))"""
    if df >= n_docs:
        return 0.0

    return max(0.0, math.log10((n_docs - df) / df))


def idf_bm25(n_docs: int, df: int) -> float:
    """BM25 idf = max(0, log10((N - df + 0.5) / (df + 0.5)))"""
    return max(0.0, math.log10((n_docs - df + 0.5) / (df + 0.5)))


IDF_FUNCTIONS: dict[str, Callable[[int, int], float]] = {
    "idf": idf_classic,
    "prob": idf_probabilistic,
}

RANKING_METHODS: tuple[str, ...] = ("idf", "prob", "bm25")


def _score_tfidf(
    reader: IndexReader,
    query: str,
    idf_function: Callable[[int, int], float],
    allowed: Optional[set[int]],
) -> dict[int, float]:
    """allowed: doc ids to score (AND), None = any match (OR)."""
    scores: dict[int, float] = {}

    for term, query_tf in Counter(tokenize(query)).items():
        entry = reader.dictionary.get(term)

        if entry is None:
            log_info(f"term not in the index: {term}")
            continue

        df, offset = entry
        query_weight = query_tf * idf_function(reader.n_docs, df)

        if query_weight == 0.0:
            continue

        for doc_id, tf in reader.read_postings(df, offset):
            if allowed is not None and doc_id not in allowed:
                continue

            scores[doc_id] = scores.get(doc_id, 0.0) + query_weight * tf_weight(tf)

    for doc_id in scores:
        norm = reader.norms[doc_id]

        if norm > 0.0:
            scores[doc_id] /= norm

    return scores


def _score_bm25(reader: IndexReader, query: str, allowed: Optional[set[int]]) -> dict[int, float]:
    scores: dict[int, float] = {}

    for term, query_tf in Counter(tokenize(query)).items():
        entry = reader.dictionary.get(term)

        if entry is None:
            log_info(f"term not in the index: {term}")
            continue

        df, offset = entry
        weight = query_tf * idf_bm25(reader.n_docs, df)

        if weight == 0.0:
            continue

        for doc_id, tf in reader.read_postings(df, offset):
            if allowed is not None and doc_id not in allowed:
                continue

            length_part = BM25_K1 * (
                1.0 - BM25_B + BM25_B * reader.lengths[doc_id] / reader.avg_length
            )
            scores[doc_id] = scores.get(doc_id, 0.0) + weight * tf * (BM25_K1 + 1.0) / (tf + length_part)

    return scores


def documents_with_all_terms(reader: IndexReader, query: str) -> set[int]:
    """Docs containing every query term. Intersects rarest term first; an unknown term -> empty."""
    entries: list[tuple[int, int]] = []

    for term in set(tokenize(query)):
        entry = reader.dictionary.get(term)

        if entry is None:
            log_info(f"term not in the index: {term}, no document contains every word")
            return set()

        entries.append(entry)

    entries.sort()  # by df
    candidates: Optional[set[int]] = None

    for df, offset in entries:
        doc_ids = {doc_id for doc_id, _ in reader.read_postings(df, offset)}
        candidates = doc_ids if candidates is None else candidates & doc_ids

        if not candidates:
            return set()

    return candidates if candidates is not None else set()


def rank(
    reader: IndexReader, query: str, method: str, top_k: int, require_all: bool = False
) -> list[tuple[int, float]]:
    """Up to top_k (doc_id, score), best first. require_all: AND filter, scores are the same as OR."""
    allowed: Optional[set[int]] = documents_with_all_terms(reader, query) if require_all else None

    if method == "bm25":
        scores = _score_bm25(reader, query, allowed)
    else:
        scores = _score_tfidf(reader, query, IDF_FUNCTIONS[method], allowed)

    # Ties -> smaller doc id, stable output.
    return heapq.nlargest(top_k, scores.items(), key=lambda item: (item[1], -item[0]))