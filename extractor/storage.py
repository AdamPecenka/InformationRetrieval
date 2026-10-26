import os

import constants
from common.log import log_alert, log_remove
from common.tsv import TsvAppender, format_row, prepare_file, read_rows


def list_pages() -> list[str]:
    """Paths of the stored athlete pages, ordered by athlete id."""
    if not os.path.isdir(constants.RAW_ATHLETES_DIR):
        return []

    names = [name for name in os.listdir(constants.RAW_ATHLETES_DIR) if name.endswith(".html")]
    names.sort(key=lambda name: (0, int(name[:-5])) if name[:-5].isdigit() else (1, 0))
    return [os.path.join(constants.RAW_ATHLETES_DIR, name) for name in names]


def read_page(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def _header_matches(path: str, header: list[str]) -> bool:
    """True when the file is missing/empty or starts with exactly this header."""
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return True

    with open(path, "r", encoding="utf-8", newline="") as handle:
        first_line = handle.readline()

    return first_line == format_row(header)


def _remove_if_exists(path: str) -> None:
    if os.path.exists(path):
        os.remove(path)


def _drop_orphan_results(done: set[str]) -> None:
    """Remove result rows of athletes that never got their athlete row (run died in between)."""
    rows, skipped = read_rows(constants.RESULTS_TSV_PATH, constants.RESULT_COLUMNS)
    kept = [row for row in rows if row[0] in done]
    dropped = len(rows) - len(kept)

    if dropped == 0 and skipped == 0:
        return

    tmp_path = constants.RESULTS_TSV_PATH + ".tmp"

    with open(tmp_path, "w", encoding="utf-8", newline="") as handle:
        handle.write(format_row(constants.RESULT_COLUMNS))

        for row in kept:
            handle.write(format_row(row))

    os.replace(tmp_path, constants.RESULTS_TSV_PATH)
    log_remove(f"dropped {dropped} orphan and {skipped} malformed rows from {constants.RESULTS_TSV_PATH}")


class ExtractedStore:
    """athletes.tsv + results.tsv, appended page by page. `done` holds the finished athlete ids."""

    def __init__(self, rebuild: bool) -> None:
        os.makedirs(constants.EXTRACTED_DIR, exist_ok=True)

        if rebuild:
            log_remove("--rebuild: dropping the existing TSVs")
            self._remove_both()
        elif not (
            _header_matches(constants.ATHLETES_TSV_PATH, constants.ATHLETE_COLUMNS)
            and _header_matches(constants.RESULTS_TSV_PATH, constants.RESULT_COLUMNS)
        ):
            log_alert("column layout changed, rebuilding the TSVs")
            self._remove_both()

        # Creates missing files and cuts a half written last line, before anything is read.
        prepare_file(constants.ATHLETES_TSV_PATH, constants.ATHLETE_COLUMNS)
        prepare_file(constants.RESULTS_TSV_PATH, constants.RESULT_COLUMNS)

        athlete_rows, _ = read_rows(constants.ATHLETES_TSV_PATH, constants.ATHLETE_COLUMNS)
        self.done: set[str] = {row[0] for row in athlete_rows}

        _drop_orphan_results(self.done)

        self._athletes = TsvAppender(constants.ATHLETES_TSV_PATH, constants.ATHLETE_COLUMNS)
        self._results = TsvAppender(constants.RESULTS_TSV_PATH, constants.RESULT_COLUMNS)

    def write(self, athlete: dict[str, str], results: list[dict[str, str]]) -> None:
        """Results first, athlete row last: the athlete row marks the page as done."""
        if results:
            self._results.append_rows([[row[column] for column in constants.RESULT_COLUMNS] for row in results])

        self._athletes.append_rows([[athlete[column] for column in constants.ATHLETE_COLUMNS]])
        self.done.add(athlete["athlete_id"])

    def close(self) -> None:
        self._athletes.close()
        self._results.close()

    @staticmethod
    def _remove_both() -> None:
        _remove_if_exists(constants.ATHLETES_TSV_PATH)
        _remove_if_exists(constants.RESULTS_TSV_PATH)