import heapq
import itertools
import math
import os
from array import array
from collections import Counter
from collections.abc import Iterator

import constants
from common.log import log_add, log_alert, log_error, log_info, log_remove
from common.tsv import format_row, read_rows
from indexer.ranking import tf_weight
from indexer.storage import POSTING
from indexer.text import tokenize

# Single-pass in-memory indexing (SPIMI), see the lecture "Single-pass in-memory indexing":
#   1. documents are read one by one and their terms are added straight into an in-memory dictionary
#      term -> postings list (no termID mapping)
#   2. when the block is "full" its terms are sorted and it is written to disk
#   3. all blocks are merged into the final dictionary + postings file
# Doc ids grow while reading and a document is never split between two blocks, so the postings of
# one term from consecutive blocks can simply be concatenated and stay sorted by doc id.


def _prepare_blocks_dir() -> None:
    if os.path.isdir(constants.INDEX_BLOCKS_DIR):
        stale = os.listdir(constants.INDEX_BLOCKS_DIR)

        for name in stale:
            os.remove(os.path.join(constants.INDEX_BLOCKS_DIR, name))

        if stale:
            log_remove(f"dropped {len(stale)} stale block files from an interrupted run")

    os.makedirs(constants.INDEX_BLOCKS_DIR, exist_ok=True)


def _load_result_texts() -> dict[str, list[str]]:
    """athlete_id -> one text per result row of the athlete (the columns of INDEX_RESULT_COLUMNS joined)."""
    if not os.path.exists(constants.RESULTS_TSV_PATH):
        log_alert(f"{constants.RESULTS_TSV_PATH} not found, indexing the athletes without their results")
        return {}

    rows, skipped = read_rows(constants.RESULTS_TSV_PATH, constants.RESULT_COLUMNS)
    indexes = [constants.RESULT_COLUMNS.index(column) for column in constants.INDEX_RESULT_COLUMNS]
    texts: dict[str, list[str]] = {}

    if skipped > 0:
        log_alert(f"skipped {skipped} malformed rows in results.tsv")

    for row in rows:
        texts.setdefault(row[0], []).append(" ".join(row[index] for index in indexes))

    log_info(f"{len(rows)} result rows of {len(texts)} athletes loaded")
    return texts


def _write_block(block: dict[str, list[int]], number: int) -> str:
    """Writes one block: lines `term<TAB>doc:tf,doc:tf,...`, terms sorted. A postings list is stored flat as doc, tf, doc, tf."""
    path = os.path.join(constants.INDEX_BLOCKS_DIR, f"block_{number:05d}.tsv")

    with open(path, "w", encoding="utf-8", newline="") as handle:
        for term in sorted(block):
            flat = block[term]
            postings = ",".join(f"{flat[position]}:{flat[position + 1]}" for position in range(0, len(flat), 2))
            handle.write(f"{term}\t{postings}\n")

    log_add(f"block {number} written, {len(block)} terms")
    return path


def _read_block(path: str, number: int) -> Iterator[tuple[str, int, str]]:
    with open(path, "r", encoding="utf-8", newline="") as handle:
        for line in handle:
            term, postings = line.rstrip("\n").split("\t", 1)
            yield term, number, postings


def _merge_blocks(block_paths: list[str], norms_squared: array) -> tuple[int, int]:
    """Merges the blocks into dictionary.tsv.tmp and postings.bin.tmp. Returns (terms, postings).

    While the postings of a term pass through, the squared length of every document vector
    (log scaled tf) is accumulated, it is needed for the Euclidean normalization.
    """
    merged = heapq.merge(*(_read_block(path, number) for number, path in enumerate(block_paths)))
    terms = 0
    postings_total = 0
    offset = 0

    with open(constants.INDEX_POSTINGS_PATH + ".tmp", "wb") as postings_file, open(
        constants.INDEX_DICTIONARY_PATH + ".tmp", "w", encoding="utf-8", newline=""
    ) as dictionary_file:
        dictionary_file.write(format_row(constants.DICTIONARY_COLUMNS))

        for term, group in itertools.groupby(merged, key=lambda entry: entry[0]):
            buffer = bytearray()
            df = 0

            for _, _, postings in group:
                for pair in postings.split(","):
                    doc_text, tf_text = pair.split(":")
                    doc_id = int(doc_text)
                    tf = int(tf_text)

                    buffer += POSTING.pack(doc_id, tf)
                    weight = tf_weight(tf)
                    norms_squared[doc_id] += weight * weight
                    df += 1

            postings_file.write(buffer)
            dictionary_file.write(f"{term}\t{df}\t{offset}\n")
            offset += len(buffer)
            postings_total += df
            terms += 1

    return terms, postings_total


def _write_docs(athlete_ids: list[str], names: list[str], lengths: array, norms_squared: array) -> None:
    with open(constants.INDEX_DOCS_PATH + ".tmp", "w", encoding="utf-8", newline="") as handle:
        handle.write(format_row(constants.DOC_COLUMNS))

        for doc_id in range(len(athlete_ids)):
            norm = math.sqrt(norms_squared[doc_id])
            row = [str(doc_id), athlete_ids[doc_id], names[doc_id], str(lengths[doc_id]), f"{norm:.6f}"]
            handle.write(format_row(row))

def build_index() -> int:
    """Rebuilds the whole index from data/extracted/athletes.tsv. One athlete row = one document."""
    if not os.path.exists(constants.ATHLETES_TSV_PATH):
        log_error(f"{constants.ATHLETES_TSV_PATH} not found, run the extractor first")
        return 1

    column_count = len(constants.ATHLETE_COLUMNS)
    id_index = constants.ATHLETE_COLUMNS.index("athlete_id")
    name_index = constants.ATHLETE_COLUMNS.index("full_name")
    text_indexes = [constants.ATHLETE_COLUMNS.index(column) for column in constants.INDEX_TEXT_COLUMNS]

    os.makedirs(constants.INDEX_DIR, exist_ok=True)
    _prepare_blocks_dir()
    result_texts = _load_result_texts()

    athlete_ids: list[str] = []
    names: list[str] = []
    lengths = array("I")  # number of tokens of every document, used by BM25
    block: dict[str, list[int]] = {}
    block_postings = 0
    block_paths: list[str] = []
    skipped = 0

    with open(constants.ATHLETES_TSV_PATH, "r", encoding="utf-8", newline="") as handle:
        if handle.readline() != format_row(constants.ATHLETE_COLUMNS):
            log_error("athletes.tsv has an unexpected header, run: python main.py extract --rebuild")
            return 1

        for line in handle:
            fields = line.rstrip("\n").split("\t")

            if len(fields) != column_count:
                skipped += 1
                continue

            doc_id = len(athlete_ids)
            athlete_ids.append(fields[id_index])
            names.append(fields[name_index])

            tokens: list[str] = []

            for index in text_indexes:
                tokens.extend(tokenize(fields[index]))

            for text in result_texts.get(fields[id_index], []):
                tokens.extend(tokenize(text))

            lengths.append(len(tokens))

            for term, tf in Counter(tokens).items():
                postings = block.get(term)

                if postings is None:
                    postings = []
                    block[term] = postings

                postings.append(doc_id)
                postings.append(tf)
                block_postings += 1

            if block_postings >= constants.INDEX_BLOCK_MAX_POSTINGS:
                block_paths.append(_write_block(block, len(block_paths)))
                block = {}
                block_postings = 0

            if len(athlete_ids) % constants.INDEX_PROGRESS_EVERY_DOCS == 0:
                log_info(f"{len(athlete_ids)} documents read")

    if block:
        block_paths.append(_write_block(block, len(block_paths)))

    if skipped > 0:
        log_alert(f"skipped {skipped} malformed rows in athletes.tsv")

    if not athlete_ids:
        log_error("no documents to index")
        return 1

    log_info(f"{len(athlete_ids)} documents, {len(block_paths)} blocks, merging")

    norms_squared = array("d", [0.0]) * len(athlete_ids)
    terms, postings_total = _merge_blocks(block_paths, norms_squared)
    _write_docs(athlete_ids, names, lengths, norms_squared)

    # All three files are complete at this point, swap them in together.
    for path in (constants.INDEX_POSTINGS_PATH, constants.INDEX_DICTIONARY_PATH, constants.INDEX_DOCS_PATH):
        os.replace(path + ".tmp", path)

    for path in block_paths:
        os.remove(path)

    os.rmdir(constants.INDEX_BLOCKS_DIR)
    log_remove(f"removed {len(block_paths)} block files")

    log_info(f"done: {len(athlete_ids)} documents, {terms} terms, {postings_total} postings")
    return 0