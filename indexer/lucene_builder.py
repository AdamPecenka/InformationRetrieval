# Runs in the PyLucene container.
import os
import time

import lucene  # noqa: F401  before any java / org.apache import
from java.nio.file import Paths
from org.apache.lucene.document import Document, Field, IntPoint, StoredField, StringField, TextField
from org.apache.lucene.index import DirectoryReader, IndexWriter, IndexWriterConfig
from org.apache.lucene.store import FSDirectory

from common.log import log_add, log_alert, log_error, log_info
from common.tsv import iter_rows
from constants.lucene import (
    LUCENE_DOC_COLUMNS,
    LUCENE_INT_FIELDS,
    LUCENE_INT_LIST_FIELDS,
    LUCENE_KEYWORD_FIELDS,
    LUCENE_NAME_COLUMNS,
    LUCENE_NAME_FIELD,
    LUCENE_PHRASE_FIELDS,
    LUCENE_PROGRESS_EVERY_DOCS,
    LUCENE_PROSE_FIELDS,
    LUCENE_VM_ARGS,
)
from indexer.lucene_analysis import fold, make_analyzer
from indexer.lucene_values import field_values, split_values, to_int


def build_document(row: dict[str, str]) -> Document:
    """One docs.tsv row -> one document, field kinds in constants/lucene.py. Empty values are skipped."""
    document = Document()

    # The only indexed key.
    document.add(StringField("doc_id", row["doc_id"], Field.Store.YES))

    # Stored only: read by lucene_compare (athlete_id) and printed by the search. athlete_id is empty for wiki_only.
    for column in ("athlete_id", "match_type", "full_name", "sports", "wiki_title"):
        if row[column] != "":
            document.add(StoredField(column, row[column]))

    for value in field_values(row, LUCENE_NAME_COLUMNS):
        document.add(TextField(LUCENE_NAME_FIELD, fold(value), Field.Store.NO))

    for field, columns in LUCENE_PHRASE_FIELDS.items():
        for value in field_values(row, columns):
            document.add(TextField(field, fold(value), Field.Store.NO))

    for field in LUCENE_PROSE_FIELDS:
        if row[field].strip() != "":
            document.add(TextField(field, fold(row[field]), Field.Store.NO))

    for field, column in LUCENE_KEYWORD_FIELDS.items():
        for value in split_values(row[column]):
            document.add(StringField(field, fold(value).lower(), Field.Store.NO))

    for field, column in LUCENE_INT_FIELDS.items():
        number = to_int(row[column])

        if number is not None:
            document.add(IntPoint(field, number))
            document.add(StoredField(field, number))

    for field, column in LUCENE_INT_LIST_FIELDS.items():
        for value in split_values(row[column]):
            number = to_int(value)

            if number is not None:
                document.add(IntPoint(field, number))

    return document


def directory_size(path: str) -> int:
    total = 0

    for folder, _, names in os.walk(path):
        for name in names:
            total += os.path.getsize(os.path.join(folder, name))

    return total


def run_lucene_indexer(docs_path: str, index_dir: str) -> int:
    if not os.path.isfile(docs_path):
        log_error(f"{docs_path} not found, run `python main.py lucene-export` on the host first")
        return 1

    lucene.initVM(vmargs=LUCENE_VM_ARGS)
    log_info(f"lucene {lucene.VERSION}")

    os.makedirs(index_dir, exist_ok=True)
    directory = FSDirectory.open(Paths.get(index_dir))
    config = IndexWriterConfig(make_analyzer())
    config.setOpenMode(IndexWriterConfig.OpenMode.CREATE)
    writer = IndexWriter(directory, config)
    started = time.perf_counter()
    added = 0
    skipped = 0

    # Streamed: docs.tsv with the wiki_only bodies is too big to hold in memory.
    for fields in iter_rows(docs_path, LUCENE_DOC_COLUMNS):
        if fields is None:
            skipped += 1
            continue

        writer.addDocument(build_document(dict(zip(LUCENE_DOC_COLUMNS, fields))))
        added += 1

        if added % LUCENE_PROGRESS_EVERY_DOCS == 0:
            log_add(f"{added} documents indexed")

    writer.commit()
    writer.close()
    elapsed = time.perf_counter() - started

    reader = DirectoryReader.open(directory)
    indexed = reader.numDocs()
    reader.close()
    directory.close()

    if skipped > 0:
        log_alert(f"skipped {skipped} malformed rows in {docs_path}")

    if added == 0:
        log_error(f"no documents in {docs_path}")
        return 1

    log_info(f"done: {indexed} documents in {elapsed:.1f} s, index size {directory_size(index_dir) / 1_000_000:.1f} MB in {index_dir}")

    if indexed != added:
        log_error(f"{added} rows read but {indexed} documents in the index")
        return 1

    return 0