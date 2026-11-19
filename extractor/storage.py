import os

from common.log import log_alert, log_remove
from common.tsv import TsvAppender, format_row, prepare_file, read_rows
from constants.common import RAW_ATHLETES_DIR
from constants.extractor import ATHLETES_TSV_PATH, ATHLETE_COLUMNS, EXTRACTED_DIR, RESULTS_TSV_PATH, RESULT_COLUMNS


def list_pages() -> list[str]:
    """Paths of the stored athlete pages, ordered by athlete id."""
    if not os.path.isdir(RAW_ATHLETES_DIR):
        return []

    names = [name for name in os.listdir(RAW_ATHLETES_DIR) if name.endswith(".html")]
    names.sort(key=lambda name: (0, int(name[:-5])) if name[:-5].isdigit() else (1, 0))
    return [os.path.join(RAW_ATHLETES_DIR, name) for name in names]


def read_page(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def _header_matches(path: str, header: list[str]) -> bool:
    """Missing / empty file counts as matching."""
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return True

    with open(path, "r", encoding="utf-8", newline="") as handle:
        first_line = handle.readline()

    return first_line == format_row(header)


def _remove_if_exists(path: str) -> None:
    if os.path.exists(path):
        os.remove(path)


def _drop_orphan_results(done: set[str]) -> None:
    """Drop result rows without an athlete row (run died between the two writes)."""
    rows, skipped = read_rows(RESULTS_TSV_PATH, RESULT_COLUMNS)
    kept = [row for row in rows if row[0] in done]
    dropped = len(rows) - len(kept)

    if dropped == 0 and skipped == 0:
        return

    tmp_path = RESULTS_TSV_PATH + ".tmp"

    with open(tmp_path, "w", encoding="utf-8", newline="") as handle:
        handle.write(format_row(RESULT_COLUMNS))

        for row in kept:
            handle.write(format_row(row))

    os.replace(tmp_path, RESULTS_TSV_PATH)
    log_remove(f"dropped {dropped} orphan and {skipped} malformed rows from {RESULTS_TSV_PATH}")


class ExtractedStore:
    """athletes.tsv + results.tsv, appended page by page. `done` holds the finished athlete ids."""

    def __init__(self, rebuild: bool) -> None:
        os.makedirs(EXTRACTED_DIR, exist_ok=True)

        if rebuild:
            log_remove("--rebuild: dropping the existing TSVs")
            self._remove_both()
        elif not (
            _header_matches(ATHLETES_TSV_PATH, ATHLETE_COLUMNS)
            and _header_matches(RESULTS_TSV_PATH, RESULT_COLUMNS)
        ):
            log_alert("column layout changed, rebuilding the TSVs")
            self._remove_both()

        # Before reading: create missing files, cut half-written last lines.
        prepare_file(ATHLETES_TSV_PATH, ATHLETE_COLUMNS)
        prepare_file(RESULTS_TSV_PATH, RESULT_COLUMNS)

        athlete_rows, _ = read_rows(ATHLETES_TSV_PATH, ATHLETE_COLUMNS)
        self.done: set[str] = {row[0] for row in athlete_rows}

        _drop_orphan_results(self.done)

        self._athletes = TsvAppender(ATHLETES_TSV_PATH, ATHLETE_COLUMNS)
        self._results = TsvAppender(RESULTS_TSV_PATH, RESULT_COLUMNS)

    def write(self, athlete: dict[str, str], results: list[dict[str, str]]) -> None:
        """Athlete row last, it marks the page done."""
        if results:
            self._results.append_rows([[row[column] for column in RESULT_COLUMNS] for row in results])

        self._athletes.append_rows([[athlete[column] for column in ATHLETE_COLUMNS]])
        self.done.add(athlete["athlete_id"])

    def close(self) -> None:
        self._athletes.close()
        self._results.close()

    @staticmethod
    def _remove_both() -> None:
        _remove_if_exists(ATHLETES_TSV_PATH)
        _remove_if_exists(RESULTS_TSV_PATH)