from collections import deque
from dataclasses import dataclass
import constants
from common.clock import utc_now_iso
from common.log import log_alert
from common.tsv import TsvAppender, read_rows

@dataclass
class FrontierEntry:
    url: str
    depth: int
    parent_url: str
    anchor_text: str
    discovered_at: str

    def to_row(self) -> list[str]:
        return [self.url, str(self.depth), self.parent_url, self.anchor_text, self.discovered_at]


class Frontier:
    def __init__(self) -> None:
        self._appender = TsvAppender(constants.FRONTIER_PATH, constants.FRONTIER_COLUMNS)
        self._seen: set[str] = set()
        self._queue: deque[FrontierEntry] = deque()
        self._loaded: list[FrontierEntry] = []
        self._read_existing()

    def _read_existing(self) -> None:
        rows, skipped = read_rows(constants.FRONTIER_PATH, constants.FRONTIER_COLUMNS)

        for row in rows:
            try:
                depth = int(row[1])
            except ValueError:
                skipped += 1
                continue

            url = row[0]

            if url in self._seen:
                continue

            self._seen.add(url)
            self._loaded.append(FrontierEntry(url, depth, row[2], row[3], row[4]))

        if skipped > 0:
            log_alert(f"skipped {skipped} malformed rows in {constants.FRONTIER_PATH}")

    def load(self, done: set[str]) -> None:
        for entry in self._loaded:
            if entry.url not in done:
                self._queue.append(entry)
        self._loaded = []

    def known_count(self) -> int:
        return len(self._seen)

    def __len__(self) -> int:
        return len(self._queue)

    def seed(self, urls: list[str]) -> None:
        now = utc_now_iso()
        self.add_many([FrontierEntry(url, 0, "", "", now) for url in urls])

    def add_many(self, entries: list[FrontierEntry]) -> int:
        fresh: list[FrontierEntry] = []
        batch_urls: set[str] = set()

        for entry in entries:
            if entry.url in self._seen or entry.url in batch_urls:
                continue

            batch_urls.add(entry.url)
            fresh.append(entry)

        if len(fresh) == 0:
            return 0

        self._appender.append_rows([entry.to_row() for entry in fresh])

        for entry in fresh:
            self._seen.add(entry.url)
            self._queue.append(entry)

        return len(fresh)

    def pop(self) -> FrontierEntry | None:
        if len(self._queue) == 0:
            return None
        return self._queue.popleft()

    def push_front(self, entry: FrontierEntry) -> None:
        self._queue.appendleft(entry)
