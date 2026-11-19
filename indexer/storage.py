from array import array

from common.tsv import read_rows
from constants.indexer import (
    DICTIONARY_COLUMNS,
    DOC_COLUMNS,
    INDEX_DICTIONARY_PATH,
    INDEX_DOCS_PATH,
    INDEX_POSTINGS_PATH,
)


class IndexReader:
    """Dictionary + docs in memory, postings read from disk on demand."""

    def __init__(self) -> None:
        dictionary_rows, _ = read_rows(INDEX_DICTIONARY_PATH, DICTIONARY_COLUMNS)
        self.dictionary: dict[str, tuple[int, int]] = {row[0]: (int(row[1]), int(row[2])) for row in dictionary_rows}
        del dictionary_rows

        doc_rows, _ = read_rows(INDEX_DOCS_PATH, DOC_COLUMNS)
        self.athlete_ids: list[str] = [row[1] for row in doc_rows]
        self.names: list[str] = [row[2] for row in doc_rows]
        self.lengths: array = array("I", (int(row[3]) for row in doc_rows))
        self.norms: array = array("d", (float(row[4]) for row in doc_rows))
        self.n_docs: int = len(doc_rows)
        self.avg_length: float = max(1.0, sum(self.lengths) / self.n_docs) if self.n_docs > 0 else 1.0

        # Binary: dictionary offsets are byte positions.
        self._postings = open(INDEX_POSTINGS_PATH, "rb")

    def read_postings(self, df: int, offset: int) -> list[tuple[int, int]]:
        """(doc_id, tf) sorted by doc_id, from the line `term<TAB>doc:tf,...` at offset."""
        self._postings.seek(offset)
        line = self._postings.readline().decode("utf-8").rstrip("\n")
        postings: list[tuple[int, int]] = []

        for pair in line.split("\t", 1)[1].split(","):
            doc_text, tf_text = pair.split(":")
            postings.append((int(doc_text), int(tf_text)))

        if len(postings) != df:
            raise ValueError(f"postings.tsv is out of sync with dictionary.tsv (df {df}, found {len(postings)}), rebuild the index")

        return postings

    def close(self) -> None:
        self._postings.close()