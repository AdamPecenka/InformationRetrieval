import os
from dataclasses import dataclass
import constants
from common.log import log_alert
from common.tsv import TsvAppender, read_rows
from crawler.policy import is_terminal_status


def write_page(identifier: str, body: bytes) -> str:
    os.makedirs(constants.RAW_ATHLETES_DIR, exist_ok=True)

    final_path = os.path.join(constants.RAW_ATHLETES_DIR, f"{identifier}.html")
    temp_path = final_path + ".tmp"

    with open(temp_path, "wb") as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())

    os.replace(temp_path, final_path)

    relative = os.path.relpath(final_path, constants.DATA_DIR)
    return relative.replace(os.sep, "/")


def _flag(value: bool) -> str:
    if value:
        return "1"
    return "0"


@dataclass
class FetchRecord:
    url: str
    status: int
    attempt: int
    fetched_at: str
    size: int
    has_bio: bool
    has_medal: bool
    stored: bool
    file: str

    def to_row(self) -> list[str]:
        return [
            self.url,
            str(self.status),
            str(self.attempt),
            self.fetched_at,
            str(self.size),
            _flag(self.has_bio),
            _flag(self.has_medal),
            _flag(self.stored),
            self.file,
        ]


@dataclass
class FetchState:
    done: set[str]
    stored_count: int
    stored_bytes: int


class FetchedLog:
    """Append-only log of every fetch attempt. The last row of a URL is its state."""

    def __init__(self) -> None:
        self._appender = TsvAppender(constants.FETCHED_PATH, constants.FETCHED_COLUMNS)

    def append(self, record: FetchRecord) -> None:
        self._appender.append_rows([record.to_row()])

    def load_state(self) -> FetchState:
        rows, skipped = read_rows(constants.FETCHED_PATH, constants.FETCHED_COLUMNS)
        last: dict[str, tuple[int, bool, int]] = {}

        for row in rows:
            try:
                status = int(row[1])
                size = int(row[4])
            except ValueError:
                skipped += 1
                continue

            last[row[0]] = (status, row[7] == "1", size)

        done: set[str] = set()
        stored_count = 0
        stored_bytes = 0

        for url, (status, stored, size) in last.items():

            if not is_terminal_status(status):
                continue

            done.add(url)

            if stored:
                stored_count += 1
                stored_bytes += size

        if skipped > 0:
            log_alert(f"skipped {skipped} malformed rows in {constants.FETCHED_PATH}")

        return FetchState(done, stored_count, stored_bytes)
