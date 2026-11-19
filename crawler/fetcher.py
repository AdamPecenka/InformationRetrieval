import time
from dataclasses import dataclass
from urllib import robotparser
import requests
from common.log import log_error, log_info
from constants.common import BASE_URL
from constants.crawler import (
    CONNECT_TIMEOUT_SECONDS,
    DEFAULT_CRAWL_DELAY_SECONDS,
    MAX_REDIRECTS,
    READ_TIMEOUT_SECONDS,
    REQUEST_HEADERS,
    ROBOTS_REFRESH_SECONDS,
    ROBOTS_RETRY_SECONDS,
    STATUS_NETWORK_ERROR,
    USER_AGENT_TOKEN,
)


@dataclass
class FetchResult:
    url: str
    status: int
    body: bytes
    content_type: str
    final_url: str
    error: str
    retry_after_seconds: float | None


def _parse_retry_after(value: str | None) -> float | None:
    """Retry-After seconds; HTTP-date form ignored."""
    if value is None:
        return None
    try:
        return float(value.strip())
    except ValueError:
        return None


class Fetcher:
    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update(REQUEST_HEADERS)
        self._session.max_redirects = MAX_REDIRECTS
        self._robots: robotparser.RobotFileParser | None = None
        self._next_robots_check: float = 0.0
        self._last_response_at: float | None = None
        self._crawl_delay: float = DEFAULT_CRAWL_DELAY_SECONDS

    @property
    def crawl_delay(self) -> float:
        return self._crawl_delay

    def apply_robots_text(self, text: str) -> None:
        parser = robotparser.RobotFileParser()
        parser.parse(text.splitlines())
        delay = parser.crawl_delay(USER_AGENT_TOKEN)

        if delay is None:
            self._crawl_delay = DEFAULT_CRAWL_DELAY_SECONDS
        else:
            self._crawl_delay = float(delay)

        self._robots = parser
        self._next_robots_check = time.monotonic() + ROBOTS_REFRESH_SECONDS

        log_info(f"robots.txt applied, crawl delay {self._crawl_delay:g}s")

    def load_robots(self) -> bool:

        result = self.fetch(BASE_URL + "/robots.txt")

        if result.status == 200:
            self.apply_robots_text(result.body.decode("utf-8", errors="replace"))
            return True

        if result.status in (404, 410):
            self.apply_robots_text("")
            return True

        reason = result.error if result.error != "" else f"HTTP {result.status}"

        log_error(f"could not load robots.txt: {reason}")

        self._next_robots_check = time.monotonic() + ROBOTS_RETRY_SECONDS

        return False

    def robots_refresh_due(self) -> bool:
        return time.monotonic() >= self._next_robots_check

    def is_allowed(self, url: str) -> bool:
        if self._robots is None:
            return False
        return self._robots.can_fetch(USER_AGENT_TOKEN, url)

    def _wait_for_slot(self) -> None:
        if self._last_response_at is None:
            return

        elapsed = time.monotonic() - self._last_response_at

        remaining = self._crawl_delay - elapsed

        if remaining > 0:
            time.sleep(remaining)

    def fetch(self, url: str) -> FetchResult:
        self._wait_for_slot()

        try:
            response = self._session.get(
                url,
                timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS),
                allow_redirects=True,
            )

        except requests.exceptions.RequestException as error:
            self._last_response_at = time.monotonic()

            return FetchResult(
                url=url,
                status=STATUS_NETWORK_ERROR,
                body=b"",
                content_type="",
                final_url=url,
                error=f"{type(error).__name__}: {error}",
                retry_after_seconds=None,
            )

        self._last_response_at = time.monotonic()

        return FetchResult(
            url=url,
            status=response.status_code,
            body=response.content,
            content_type=response.headers.get("Content-Type", ""),
            final_url=response.url,
            error="",
            retry_after_seconds=_parse_retry_after(response.headers.get("Retry-After")),
        )
