import struct
from array import array
from collections.abc import Iterator

import constants
from common.tsv import read_rows

POSTING = struct.Struct(constants.POSTING_FORMAT)


class IndexReader:
    """The dictionary and the document table live in memory, postings lists are read from disk on demand."""

    def __init__(self) -> None:
        dictionary_rows, _ = read_rows(constants.INDEX_DICTIONARY_PATH, constants.DICTIONARY_COLUMNS)
        self.dictionary: dict[str, tuple[int, int]] = {row[0]: (int(row[1]), int(row[2])) for row in dictionary_rows}
        del dictionary_rows

        doc_rows, _ = read_rows(constants.INDEX_DOCS_PATH, constants.DOC_COLUMNS)
        self.athlete_ids: list[str] = [row[1] for row in doc_rows]
        self.names: list[str] = [row[2] for row in doc_rows]
        self.lengths: array = array("I", (int(row[3]) for row in doc_rows))
        self.norms: array = array("d", (float(row[4]) for row in doc_rows))
        self.n_docs: int = len(doc_rows)
        self.avg_length: float = max(1.0, sum(self.lengths) / self.n_docs) if self.n_docs > 0 else 1.0

        self._postings = open(constants.INDEX_POSTINGS_PATH, "rb")

    def read_postings(self, df: int, offset: int) -> Iterator[tuple[int, int]]:
        self._postings.seek(offset)
        data = self._postings.read(df * POSTING.size)
        return POSTING.iter_unpack(data)

    def close(self) -> None:
        self._postings.close()