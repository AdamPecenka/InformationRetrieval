import heapq
import math
from collections import Counter
from typing import Callable

import constants
from common.log import log_info
from indexer.storage import IndexReader
from indexer.text import tokenize

# tf-idf rankings follow the worked example in the lecture ("Príklad na skóre dokumentu"):
#   w(t,q) = tf(t,q) * idf(t)                      query side, natural tf
#   w(t,d) = (1 + log10 tf(t,d)) / ||d||           document side, log scaling + Euclid norm
#   Score(q,d) = sum over t in q of w(t,q) * w(t,d)
# ||d|| is the length of the log-tf vector of the document (stored in docs.tsv).
# The two idf methods below are the ones from "Modifikácie df_t - Sumarizácia".
#
# bm25 follows "Okapi BM25 score":
#   Score(q,d) = sum over t in q of idf(t) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * |d| / avg|d|))
#   idf(t) = log10((N - df + 0.5) / (df + 0.5)), set to 0 when negative (the first fix on the slide:
#   terms in more than half of the documents are ignored)


def tf_weight(tf: int) -> float:
    """Logarithmic scaling: 1 + log10(tf) for tf > 0, else 0."""
    if tf <= 0:
        return 0.0

    return 1.0 + math.log10(tf)


def idf_classic(n_docs: int, df: int) -> float:
    """idf = log10(N / df)"""
    return math.log10(n_docs / df)


def idf_probabilistic(n_docs: int, df: int) -> float:
    """probabilistic idf = max(0, log10((N - df) / df)); terms in more than half of the documents get 0"""
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


def _score_tfidf(reader: IndexReader, query: str, idf_function: Callable[[int, int], float]) -> dict[int, float]:
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
            scores[doc_id] = scores.get(doc_id, 0.0) + query_weight * tf_weight(tf)

    for doc_id in scores:
        norm = reader.norms[doc_id]

        if norm > 0.0:
            scores[doc_id] /= norm

    return scores


def _score_bm25(reader: IndexReader, query: str) -> dict[int, float]:
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
            length_part = constants.BM25_K1 * (
                1.0 - constants.BM25_B + constants.BM25_B * reader.lengths[doc_id] / reader.avg_length
            )
            scores[doc_id] = scores.get(doc_id, 0.0) + weight * tf * (constants.BM25_K1 + 1.0) / (tf + length_part)

    return scores


def rank(reader: IndexReader, query: str, method: str, top_k: int) -> list[tuple[int, float]]:
    """Returns up to top_k (doc_id, score) pairs, best first. Only documents with a non-zero score."""
    if method == "bm25":
        scores = _score_bm25(reader, query)
    else:
        scores = _score_tfidf(reader, query, IDF_FUNCTIONS[method])

    # Ties are broken by the smaller doc id so the output is stable between runs.
    return heapq.nlargest(top_k, scores.items(), key=lambda item: (item[1], -item[0]))