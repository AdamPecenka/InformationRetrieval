import os

from constants.common import BASE_URL, DATA_DIR

# ---- paths ----
CRAWLER_DIR: str = os.path.join(DATA_DIR, "crawler")
FRONTIER_PATH: str = os.path.join(CRAWLER_DIR, "frontier.tsv")
FETCHED_PATH: str = os.path.join(CRAWLER_DIR, "fetched.tsv")

SEED_URLS: list[str] = [BASE_URL + "/"]

# ---- identity ----
CONTACT: str = "xpecenka@stuba.sk"
USER_AGENT_TOKEN: str = "VINF-student-crawler"
USER_AGENT: str = f"{USER_AGENT_TOKEN}/1.0 (course project; contact: {CONTACT})"
REQUEST_HEADERS: dict[str, str] = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html",
    "Accept-Language": "en",
}

# ---- timing ----
CONNECT_TIMEOUT_SECONDS: float = 5.0
READ_TIMEOUT_SECONDS: float = 30.0
DEFAULT_CRAWL_DELAY_SECONDS: float = 10.0  # used when robots.txt has no Crawl-delay
ROBOTS_REFRESH_SECONDS: float = 24 * 60 * 60
ROBOTS_RETRY_SECONDS: float = 10 * 60
MAX_REDIRECTS: int = 3

# ---- retries ----
MAX_ATTEMPTS: int = 3
BACKOFF_BASE_SECONDS: float = float(os.environ.get("VINF_BACKOFF_BASE", "60"))
BACKOFF_CAP_SECONDS: float = 3600.0

PROGRESS_EVERY_FETCHES: int = 25

# ---- TSV layouts ----
FRONTIER_COLUMNS: list[str] = ["url", "depth", "parent_url", "anchor_text", "discovered_at"]
FETCHED_COLUMNS: list[str] = [
    "url",
    "status",
    "attempt",
    "fetched_at",
    "bytes",
    "has_bio",
    "has_medal",
    "stored",
    "file",
]

# ---- pseudo statuses in fetched.tsv ----
# <= 0: outcome without an HTTP status.
STATUS_NETWORK_ERROR: int = 0
STATUS_ROBOTS_DISALLOWED: int = -1
STATUS_OFFSITE_REDIRECT: int = -2
STATUS_GAVE_UP: int = -3
