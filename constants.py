import os
import re

# ---- paths ----
ROOT_DIR: str = os.path.dirname(os.path.abspath(__file__))
DATA_DIR: str = os.environ.get("VINF_DATA_DIR", os.path.join(ROOT_DIR, "data"))
CRAWLER_DIR: str = os.path.join(DATA_DIR, "crawler")
FRONTIER_PATH: str = os.path.join(CRAWLER_DIR, "frontier.tsv")
FETCHED_PATH: str = os.path.join(CRAWLER_DIR, "fetched.tsv")
RAW_ATHLETES_DIR: str = os.path.join(DATA_DIR, "raw", "athletes")

# ---- site ----
BASE_URL: str = os.environ.get("VINF_BASE_URL", "https://www.olympedia.org").rstrip("/")
SEED_URLS: list[str] = [BASE_URL + "/"]
URL_WHITELIST: re.Pattern[str] = re.compile(
    "^" + re.escape(BASE_URL) + r"/(athletes/\d+|editions(/\d+(/medal)?)?|countries(/[A-Z]{3})?)$"
)
ATHLETE_URL_PATTERN: re.Pattern[str] = re.compile("^" + re.escape(BASE_URL) + r"/athletes/(\d+)$")

# ---- which athlete pages are stored ----
# A page is stored when it has a "Biography" section AND at least one medal.
BIO_HEADING_PATTERN: re.Pattern[str] = re.compile(r"<h2>\s*Biography\s*</h2>")
MEDAL_SPAN_PATTERN: re.Pattern[str] = re.compile(r'<span class="(?:Gold|Silver|Bronze)">')

# ---- crawler identity ----
# Set CONTACT to something that lets the site owner reach you (school email,
# project page). The crawler prints an alert at startup while it is CHANGE-ME.
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
DEFAULT_CRAWL_DELAY_SECONDS: float = 10.0
ROBOTS_REFRESH_SECONDS: float = 24 * 60 * 60
ROBOTS_RETRY_SECONDS: float = 10 * 60
MAX_REDIRECTS: int = 3

# ---- retries ----
MAX_ATTEMPTS: int = 3
BACKOFF_BASE_SECONDS: float = float(os.environ.get("VINF_BACKOFF_BASE", "60"))
BACKOFF_CAP_SECONDS: float = 3600.0

# ---- progress output ----
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

# ---- pseudo HTTP statuses written to fetched.tsv ----
# Real HTTP statuses are positive. These mark outcomes that had no HTTP status.
STATUS_NETWORK_ERROR: int = 0
STATUS_ROBOTS_DISALLOWED: int = -1
STATUS_OFFSITE_REDIRECT: int = -2
STATUS_GAVE_UP: int = -3
