# Runs in the PyLucene container.
import os
import time

import lucene  # noqa: F401  before any java / org.apache import
from java.nio.file import Paths
from org.apache.lucene.document import Document, Field, IntPoint, StoredField, StringField, TextField
from org.apache.lucene.index import DirectoryReader, IndexWriter, IndexWriterConfig
from org.apache.lucene.store import FSDirectory

from common.log import log_add, log_alert, log_error, log_info
from common.tsv import read_rows
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
from indexer.lucene_values import split_values, to_int


def build_document(row: dict[str, str]) -> Document:
    """One athlete -> one document, field kinds in constants/lucene.py."""
    document = Document()

    # Printed by the search; only athlete_id is searchable.
    document.add(StringField("athlete_id", row["athlete_id"], Field.Store.YES))
    document.add(StoredField("full_name", row["full_name"]))
    document.add(StoredField("sports", row["sports"]))

    for column in LUCENE_NAME_COLUMNS:
        for value in split_values(row[column]):
            document.add(TextField(LUCENE_NAME_FIELD, fold(value), Field.Store.NO))

    for field, column in LUCENE_PHRASE_FIELDS.items():
        for value in split_values(row[column]):
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

    rows, skipped = read_rows(docs_path, LUCENE_DOC_COLUMNS)

    if skipped > 0:
        log_alert(f"skipped {skipped} malformed rows in {docs_path}")

    if len(rows) == 0:
        log_error("no documents to index")
        return 1

    log_info(f"{len(rows)} documents read from {docs_path}")

    lucene.initVM(vmargs=LUCENE_VM_ARGS)
    log_info(f"lucene {lucene.VERSION}")

    os.makedirs(index_dir, exist_ok=True)
    directory = FSDirectory.open(Paths.get(index_dir))
    config = IndexWriterConfig(make_analyzer())
    config.setOpenMode(IndexWriterConfig.OpenMode.CREATE)
    writer = IndexWriter(directory, config)
    started = time.perf_counter()

    for position, fields in enumerate(rows, start=1):
        writer.addDocument(build_document(dict(zip(LUCENE_DOC_COLUMNS, fields))))

        if position % LUCENE_PROGRESS_EVERY_DOCS == 0:
            log_add(f"{position} documents indexed")

    writer.commit()
    writer.close()
    elapsed = time.perf_counter() - started

    reader = DirectoryReader.open(directory)
    indexed = reader.numDocs()
    reader.close()
    directory.close()

    log_info(f"done: {indexed} documents in {elapsed:.1f} s, index size {directory_size(index_dir) / 1_000_000:.1f} MB in {index_dir}")

    if indexed != len(rows):
        log_error(f"{len(rows)} rows read but {indexed} documents in the index")
        return 1

    return 0