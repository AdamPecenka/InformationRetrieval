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

# ---- extractor: output ----
EXTRACTED_DIR: str = os.path.join(DATA_DIR, "extracted")
ATHLETES_TSV_PATH: str = os.path.join(EXTRACTED_DIR, "athletes.tsv")
RESULTS_TSV_PATH: str = os.path.join(EXTRACTED_DIR, "results.tsv")
EXTRACT_PROGRESS_EVERY_PAGES: int = 1000
EXTRACT_MAX_PAGE_WARNINGS: int = 10
LIST_SEPARATOR: str = " | "

ATHLETE_COLUMNS: list[str] = [
    "athlete_id",
    "full_name",
    "given_names",
    "family_name",
    "used_name",
    "other_names",
    "original_name",
    "nickname",
    "sex",
    "roles",
    "born_date",
    "born_place",
    "born_country",
    "died_date",
    "died_place",
    "died_country",
    "height_cm",
    "weight_kg",
    "affiliations",
    "noc_codes",
    "noc_names",
    "nationality_codes",
    "nationality_names",
    "medals_gold",
    "medals_silver",
    "medals_bronze",
    "medals_total",
    "other_participations",
    "personal_bests",
    "world_records",
    "post_career",
    "career_events",
    "list_mentions",
    "biography",
]

RESULT_COLUMNS: list[str] = [
    "athlete_id",
    "games",
    "year",
    "season",
    "sport",
    "discipline",
    "event",
    "team",
    "position",
    "medal",
]

# ---- extractor: page structure ----
# Section titles (<h2>, lower-cased) of a stored athlete page.
SECTION_BIOGRAPHICAL: str = "biographical information"
SECTION_BIOGRAPHY: str = "biography"
SECTION_RESULTS: str = "results"
SECTION_OTHER_PARTICIPATIONS: str = "other participations"
SECTION_LIST_MENTIONS: str = "list mentions"

# Row labels of the "Biographical information" table.
BIODATA_LABELS: frozenset[str] = frozenset(
    {
        "Roles",
        "Sex",
        "Full name",
        "Used name",
        "Other names",
        "Original name",
        "Nickname",
        "Born",
        "Died",
        "Measurements",
        "Affiliations",
        "NOC",
        "Nationality",
    }
)

MAX_COLSPAN: int = 12
BULLET: str = "\u2022"

COMMENT_PATTERN: re.Pattern[str] = re.compile(r"(?s)<!--.*?-->")
SCRIPT_STYLE_PATTERN: re.Pattern[str] = re.compile(r"(?is)<(script|style)\b.*?</\1>")
TAG_PATTERN: re.Pattern[str] = re.compile(r"<[^>]+>")
H2_PATTERN: re.Pattern[str] = re.compile(r"(?is)<h2\b[^>]*>(.*?)</h2>")
TABLE_PATTERN: re.Pattern[str] = re.compile(r"(?is)<table\b[^>]*>(.*?)</table>")
ROW_PATTERN: re.Pattern[str] = re.compile(r"(?is)<tr\b[^>]*>(.*?)</tr>")
CELL_PATTERN: re.Pattern[str] = re.compile(r"(?is)<(t[hd])\b([^>]*)>(.*?)</\1>")
COLSPAN_PATTERN: re.Pattern[str] = re.compile(r"(?i)colspan\s*=\s*[\"']?(\d+)")
PARAGRAPH_PATTERN: re.Pattern[str] = re.compile(r"(?is)<p\b[^>]*>(.*?)</p>")
LIST_ITEM_PATTERN: re.Pattern[str] = re.compile(r"(?is)<li\b[^>]*>(.*?)</li>")
ANCHOR_PATTERN: re.Pattern[str] = re.compile(r"(?is)<a\b[^>]*>(.*?)</a>")
COUNTRY_HREF_PATTERN: re.Pattern[str] = re.compile(r'href="/countries/([A-Za-z0-9]{2,3})"')

# ---- extractor: values ----
MEDAL_NAMES: tuple[str, ...] = ("Gold", "Silver", "Bronze")
MEDAL_COUNT_PATTERN: re.Pattern[str] = re.compile(
    r"(?is)<t[hd]\b[^>]*>(?:\s|<[^>]+>)*(Gold|Silver|Bronze|Total)(?:\s|<[^>]+>)*</t[hd]>"
    r"\s*<t[hd]\b[^>]*>\s*(\d+)\s*</t[hd]>"
)
MEDAL_TEXT_PATTERN: re.Pattern[str] = re.compile(r"^(Gold|Silver|Bronze)$")
MEDAL_SPAN_PATTERN: re.Pattern[str] = re.compile(r'<span class="(Gold|Silver|Bronze)">')

HEIGHT_PATTERN: re.Pattern[str] = re.compile(r"(\d+)\s*cm")
WEIGHT_PATTERN: re.Pattern[str] = re.compile(r"(\d+)\s*kg")
AGED_PATTERN: re.Pattern[str] = re.compile(r"\s*\(aged\s+[^)]*\)")
TRAILING_NOC_PATTERN: re.Pattern[str] = re.compile(r"^(?P<place>.*?)\s*\((?P<noc>[A-Z]{3})\)\s*$")
DATE_DMY_PATTERN: re.Pattern[str] = re.compile(r"^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$")
DATE_MY_PATTERN: re.Pattern[str] = re.compile(r"^([A-Za-z]+)\s+(\d{4})$")
DATE_Y_PATTERN: re.Pattern[str] = re.compile(r"^(\d{4})$")
MONTHS: dict[str, int] = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
PERSONAL_BEST_PATTERN: re.Pattern[str] = re.compile(r"(?im)^\s*Personal Bests?\s*:\s*(.+?)\s*$")

# Results table: "1980 Summer Olympics", "Basketball, Women (Olympic)", "Diving (Aquatics)".
GAMES_PATTERN: re.Pattern[str] = re.compile(r"^(\d{4})\s+(Summer|Winter|Intercalated)\b")
EVENT_STATUS_PATTERN: re.Pattern[str] = re.compile(r"\s*\([^()]*\)\s*$")
DISCIPLINE_PATTERN: re.Pattern[str] = re.compile(r"^(?P<discipline>.*?)\s*\((?P<sport>[^()]*)\)\s*$")

# ---- extractor: biography mining (rule based, one hit = one whole sentence) ----
SENTENCE_BOUNDARY_PATTERN: re.Pattern[str] = re.compile(r"(?<=[.!?])\s+(?=[\"'(]?[A-Z0-9])")
WORLD_RECORD_PATTERN: re.Pattern[str] = re.compile(r"\bworld[- ]records?\b", re.IGNORECASE)

CAREER_EVENT_RULES: list[tuple[str, re.Pattern[str]]] = [
    (
        "retirement",
        re.compile(
            r"\bretir(?:ed|es|ing|ement)\b|\bended (?:his|her|their) (?:sporting |competitive )?career\b"
            r"|\bquit (?:the sport|competing|competition)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "comeback",
        re.compile(
            r"\bcomeback\b|\bcame out of retirement\b|\bun-?retired\b"
            r"|\breturned to (?:competition|competing|the sport|the national team|racing|the ring|the pool|the track)\b"
            r"|\bresumed (?:his|her|their)? ?(?:career|competing|training)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "injury",
        re.compile(
            r"\binjur(?:y|ies|ed)\b|\bbroke (?:his|her|their) (?:leg|arm|ankle|wrist|collarbone|back|neck|foot|knee)\b"
            r"|\bsurgery\b|\btorn\b",
            re.IGNORECASE,
        ),
    ),
]

POST_CAREER_CUE_PATTERN: re.Pattern[str] = re.compile(
    r"\bafter (?:his|her|their) (?:retirement|career|competitive career|sporting career|playing career)\b"
    r"|\bafter retiring\b|\bupon (?:his|her|their) retirement\b|\bfollowing (?:his|her|their) retirement\b"
    r"|\bpost-career\b|\bin later life\b|\blater (?:career|life|years)\b|\bwent into\b"
    r"|\blater (?:became|worked|served|was elected|was appointed|moved|ran)\b"
    r"|\bafter (?:leaving|quitting) (?:the )?(?:sport|competition)\b",
    re.IGNORECASE,
)
ROLE_VERB_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:became|worked as|served as|was elected|was appointed|ran for|opened (?:a|his|her)|founded)\b",
    re.IGNORECASE,
)
OCCUPATION_RULES: list[tuple[str, re.Pattern[str]]] = [
    (
        "politician",
        re.compile(
            r"\bpolitic|member of parliament|\bsenator|\bmayor\b|\bminister\b|\bdeputy\b|\bcouncillor|\bgovernor\b|\bparliament|\blegislat",
            re.IGNORECASE,
        ),
    ),
    ("coach", re.compile(r"\bcoach|\btrainer\b|\bmanager\b|\breferee", re.IGNORECASE)),
    (
        "physician",
        re.compile(r"\bphysician|\bdoctor\b|\bsurgeon|\bdentist|\bmedical (?:doctor|practice)|\b\w+ologist\b", re.IGNORECASE),
    ),
    ("engineer", re.compile(r"\bengineer", re.IGNORECASE)),
    ("lawyer", re.compile(r"\blawyer|\battorney|\bjudge\b|\bprosecutor", re.IGNORECASE)),
    ("teacher", re.compile(r"\bteacher|\bprofessor|\blecturer|\bschool principal", re.IGNORECASE)),
    (
        "businessperson",
        re.compile(
            r"\bbusiness(?:man|woman|person)|\bentrepreneur|\bran a (?:company|business)|\bfounded a company",
            re.IGNORECASE,
        ),
    ),
    ("military", re.compile(r"\bofficer\b|\bcolonel\b|\bmajor general\b|\barmy\b|\bnavy\b|\bair force\b", re.IGNORECASE)),
    ("police", re.compile(r"\bpolice", re.IGNORECASE)),
    (
        "artist",
        re.compile(r"\bactor\b|\bactress\b|\bsinger\b|\bmusician\b|\bpainter\b|\bartist\b|\bfilm\b", re.IGNORECASE),
    ),
    (
        "journalist",
        re.compile(r"\bjournalist|\bcommentator|\bbroadcaster|\bwriter\b|\bauthor\b", re.IGNORECASE),
    ),
    (
        "sports official",
        re.compile(
            r"\bIOC member|\bpresident of the\b|\bchairman|\bsecretary[- ]general|\bfederation official"
            r"|\bsports (?:official|administrator)|\badministrator\b",
            re.IGNORECASE,
        ),
    ),
]

# ---- indexer ----
INDEX_DIR: str = os.path.join(DATA_DIR, "index")
INDEX_DICTIONARY_PATH: str = os.path.join(INDEX_DIR, "dictionary.tsv")
INDEX_POSTINGS_PATH: str = os.path.join(INDEX_DIR, "postings.bin")
INDEX_DOCS_PATH: str = os.path.join(INDEX_DIR, "docs.tsv")
INDEX_BLOCKS_DIR: str = os.path.join(INDEX_DIR, "blocks")
# A SPIMI block goes to disk once it holds this many postings (stand-in for "memory is full").
INDEX_BLOCK_MAX_POSTINGS: int = 2_000_000
INDEX_PROGRESS_EVERY_DOCS: int = 5000

TOKEN_PATTERN: re.Pattern[str] = re.compile(r"[^\W_]+")
POSTING_FORMAT: str = "<II"  # one posting: doc id, tf (little endian uint32 each)

DICTIONARY_COLUMNS: list[str] = ["term", "df", "offset"]
DOC_COLUMNS: list[str] = ["doc_id", "athlete_id", "full_name", "length", "norm"]

# BM25 parameters (v prednaske: k1 = <1.2; 2>, b = 0.75).
BM25_K1: float = 1.2
BM25_B: float = 0.3

# Columns of athletes.tsv whose text goes into the index (one document = one athlete).
INDEX_TEXT_COLUMNS: list[str] = [
    "full_name",
    "used_name",
    "other_names",
    "original_name",
    "nickname",
    "roles",
    "born_place",
    "born_country",
    "died_place",
    "died_country",
    "affiliations",
    "noc_codes",
    "noc_names",
    "nationality_names",
    "other_participations",
    "personal_bests",
    "post_career",
    "career_events",
    "list_mentions",
    "biography",
]

# Columns of results.tsv whose text is added to the document of the athlete (joined on athlete_id).
INDEX_RESULT_COLUMNS: list[str] = ["year", "season", "sport", "discipline", "event", "medal"]

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
