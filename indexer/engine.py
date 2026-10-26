import os

import constants
from common.log import log_error
from indexer.builder import build_index
from indexer.ranking import RANKING_METHODS, rank
from indexer.storage import IndexReader
from indexer.text import tokenize


def run_indexer() -> int:
    return build_index()


def run_search(query: str, top_k: int, method: str) -> int:
    """Prints the top_k athletes for the query, once per ranking method ("all" prints every method)."""
    for path in (constants.INDEX_DICTIONARY_PATH, constants.INDEX_POSTINGS_PATH, constants.INDEX_DOCS_PATH):
        if not os.path.exists(path):
            log_error("no index found, run: python main.py index")
            return 1

    if not tokenize(query):
        log_error("the query has no searchable words")
        return 1

    methods = list(RANKING_METHODS) if method == "all" else [method]
    reader = IndexReader()

    try:
        if reader.n_docs == 0:
            log_error("the index is empty or in an old format, run: python main.py index")
            return 1

        for current in methods:
            results = rank(reader, query, current, top_k)
            print(f"--- ranking '{current}': {len(results)} hits ---")

            for position, (doc_id, score) in enumerate(results, start=1):
                print(f"{position:>3}. {score:8.4f}  {reader.athlete_ids[doc_id]:>8}  {reader.names[doc_id]}")
    finally:
        reader.close()

    return 0