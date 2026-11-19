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
INDEX_POSTINGS_PATH: str = os.path.join(INDEX_DIR, "postings.tsv")
INDEX_DOCS_PATH: str = os.path.join(INDEX_DIR, "docs.tsv")
INDEX_BLOCKS_DIR: str = os.path.join(INDEX_DIR, "blocks")
# A SPIMI block goes to disk once it holds this many postings (stand-in for "memory is full").
INDEX_BLOCK_MAX_POSTINGS: int = 2_000_000
INDEX_PROGRESS_EVERY_DOCS: int = 5000

TOKEN_PATTERN: re.Pattern[str] = re.compile(r"[^\W_]+")

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

# ---- wikipedia dump ----
WIKI_DUMP_PATH: str = os.environ.get("VINF_WIKI_DUMP")
WIKI_DIR: str = os.path.join(DATA_DIR, "wiki")
WIKI_SLICE_PATH: str = os.path.join(WIKI_DIR, "slice.xml")
WIKI_PAGES_PATH: str = os.path.join(WIKI_DIR, "pages_parquet")
WIKI_SLICE_PAGES: int = 20000

# ---- spark ----
SPARK_XML_PACKAGE: str = "com.databricks:spark-xml_2.12:0.18.0"
SPARK_DRIVER_MEMORY: str = os.environ.get("VINF_SPARK_DRIVER_MEMORY", "4g")
SPARK_LOCAL_DIR: str = os.environ.get("VINF_SPARK_TMP", "")

WIKI_BIO_REGEX: str = r"(?i)\[\[category:\d{1,4}( bc)? births|\|\s*birth_date\s*="

# ---- wikipedia: relevance filter (stage 2) ----
WIKI_FULL_PAGES_PATH: str = os.path.join(WIKI_DIR, "pages_full_parquet")
WIKI_RELEVANT_PATH: str = os.path.join(WIKI_DIR, "pages_relevant_parquet")
WIKI_AUDIT_ATHLETES_PATH: str = os.path.join(DATA_DIR, "extracted", "athletes.tsv")
WIKI_SAMPLES_DIR: str = os.path.join(WIKI_DIR, "samples")

# Java regexes as plain strings for Spark's rlike / regexp_extract (find semantics, not a full match).
# An article is kept when ANY of the flags built from them fires (see wiki/relevance.py), so the patterns
# are deliberately generous: keeping a page that is not needed costs disk, dropping a needed one breaks the join.
#
# Words inside a category name are delimited by "not a letter" instead of \b, because \b treats "_" as a word
# character and "Year_of_birth_missing" would slip through. The same lookarounds keep "Childbirth",
# "Birth control" and "Death metal" out.
_NOT_AFTER_LETTER: str = r"(?<![a-z])"
_NOT_BEFORE_LETTER: str = r"(?![a-z])"
_CATEGORY_OPEN: str = r"\[\[\s*category\s*:[^\]\n]*"

# Person, from a category: "1986 births", "1990 deaths", "Deaths from cancer in Texas", "384 BC births",
# "Year of birth missing", "Date of death unknown", "Living people".
WIKI_PERSON_CATEGORY_REGEX: str = (
    r"(?i)" + _CATEGORY_OPEN + r"(?:"
    + _NOT_AFTER_LETTER + r"(?:births|deaths|living[ _]people)" + _NOT_BEFORE_LETTER
    + r"|" + _NOT_AFTER_LETTER + r"(?:year|date)[ _]of[ _](?:birth|death)" + _NOT_BEFORE_LETTER
    + r")"
)

# Person, from the infobox or a template: "| birth_date =", "| birthdate =", "| born =", "| date_of_birth =",
# "{{birth date|...}}", "{{birth-date and age|...}}", "{{bda|...}}". This is the fallback for a page that has
# no births / deaths / living category.
WIKI_PERSON_INFOBOX_REGEX: str = (
    r"(?i)\|\s*(?:birth[ _]?date|date[ _]?of[ _]?birth|birth[ _]?year|born)\s*="
    r"|\{\{\s*(?:birth[ _-]?date|birth[ _-]?year|birth[ _-]based|bda|b-da|dob)\b"
)

# Olympics in the title: "Germany at the 1976 Summer Olympics", "Olympic Games", "1906 Intercalated Games".
# Paralympic is deliberately left out (Olympedia covers the Olympics). "Olympia, Washington" does not match.
WIKI_OLYMPIC_TITLE_REGEX: str = r"(?i)\bolympic|intercalated games"

# Olympics in a category: "Competitors at the 1976 Summer Olympics", "Olympic medalists in swimming",
# "Olympians ...", "Ancient Olympic competitors", "Olympic stadiums".
WIKI_OLYMPIC_CATEGORY_REGEX: str = (
    r"(?i)" + _CATEGORY_OPEN
    + _NOT_AFTER_LETTER + r"(?:olympics?|olympians?|intercalated[ _]games)" + _NOT_BEFORE_LETTER
)

# A medal template that mentions the Olympics: "{{MedalCompetition | [[Olympic Games]] ...}}". A guess at how
# infoboxes write medals; the filter reports how many pages only this rule catches.
WIKI_OLYMPIC_MEDAL_REGEX: str = r"(?i)\{\{\s*medal[^}\n]*" + _NOT_AFTER_LETTER + r"olympic"

# A link to Olympedia, as an external link, a reference, or the {{Olympedia}} template.
WIKI_OLYMPEDIA_LINK_REGEX: str = r"(?i)olympedia\.org|\{\{\s*olympedia" + _NOT_BEFORE_LETTER

# The Olympedia athlete ids on a page, for an exact join. Both patterns have one group and are used with
# regexp_extract_all, so a page that cites several athletes (a date page, a list) yields several ids and
# is not given an id at all (see wiki/relevance.py).
# From a URL:
WIKI_OLYMPEDIA_URL_ID_REGEX: str = r"(?i)olympedia\.org/athletes/(\d+)"
# From a template, the first number inside it, whatever the parameter layout ("|91889", "|id=91889",
# "|athlete|91889"). A bare {{Olympedia}} (id taken from Wikidata) carries no number and gives no id.
WIKI_OLYMPEDIA_TEMPLATE_ID_REGEX: str = r"(?i)\{\{\s*olympedia" + _NOT_BEFORE_LETTER + r"[^}\n]*?\b(\d+)\b"

# ---- wikipedia: attribute extraction (stage 3) ----
WIKI_PEOPLE_PATH: str = os.path.join(WIKI_DIR, "people_parquet")

# Only the start of an article goes to the Python extractor: the infobox, the medal table and the lead
# section are all there. The category lines come from the whole article (see WIKI_CATEGORY_NAME_REGEX).
WIKI_HEAD_CHARS: int = 40000
WIKI_LEAD_MAX_CHARS: int = 1500
# Sections after the lead are kept only when their heading names a biography-like part (see WIKI_WANTED_SECTION_PATTERN).
WIKI_SECTION_MAX_CHARS: int = 3000
WIKI_BODY_MAX_CHARS: int = 8000

# Category names of an article, group 1. Java regex for Spark's regexp_extract_all.
WIKI_CATEGORY_NAME_REGEX: str = r"(?i)\[\[\s*category\s*:\s*([^\]|\n]+)"

# ---- markup clean-up (Python re) ----
WIKI_COMMENT_PATTERN: re.Pattern[str] = re.compile(r"(?s)<!--.*?-->")
WIKI_REF_PATTERN: re.Pattern[str] = re.compile(r"(?is)<ref\b[^>]*?/>|<ref\b[^>]*>.*?</ref>")
WIKI_BREAK_PATTERN: re.Pattern[str] = re.compile(r"(?i)<br\s*/?>")
WIKI_TAG_PATTERN: re.Pattern[str] = re.compile(r"<[^>]+>")
WIKI_LINK_PATTERN: re.Pattern[str] = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]")      # [[a|b]] and [[b]] -> b
WIKI_EXTERNAL_LINK_PATTERN: re.Pattern[str] = re.compile(r"\[https?://\S+\s*([^\]]*)\]")  # [http://x text] -> text
WIKI_INNER_TEMPLATE_PATTERN: re.Pattern[str] = re.compile(r"\{\{([^{}]*)\}\}")           # a template with no template inside
WIKI_BULLET_PATTERN: re.Pattern[str] = re.compile(r"\s*\n\s*\*\s*")
WIKI_HEADING_PATTERN: re.Pattern[str] = re.compile(r"(?m)^==")                                        # first "==Heading==" ends the lead
WIKI_EMPTY_PARENTHESES_PATTERN: re.Pattern[str] = re.compile(r"\(\s*[;,\u2013\-]?\s*\)")             # "( )" left behind by a dropped date template
# A level-2 heading line "== Early life ==" (not "=== sub ===") and the markers of any heading line.
WIKI_SECTION_PATTERN: re.Pattern[str] = re.compile(r"(?m)^==(?!=)\s*(.+?)\s*==\s*$")
WIKI_HEADING_MARKUP_PATTERN: re.Pattern[str] = re.compile(r"(?m)^(=+)\s*(.+?)\s*\1\s*$")
WIKI_TABLE_PATTERN: re.Pattern[str] = re.compile(r"(?s)\{\|.*?\|\}")
# Headings worth keeping: Biography, Early life, Career, Playing career, Olympic career, Personal life, Later life, ...
WIKI_WANTED_SECTION_PATTERN: re.Pattern[str] = re.compile(
    r"(?i)\b(?:biography|early (?:life|years)|childhood|background|education|career|olympics?|personal life|later (?:life|years)|life|death|achievements?)\b"
)
WIKI_STRAY_OPENING_PATTERN: re.Pattern[str] = re.compile(r"\(\s*[;,]\s*")                             # "(; Greek" -> "(Greek"
WIKI_STRAY_SEPARATOR_PATTERN: re.Pattern[str] = re.compile(r"([;,])\s*[;,]\s*")                     # ", ;" -> ","
WIKI_LEAD_IMAGE_PATTERN: re.Pattern[str] = re.compile(r"(?i)^\[\[\s*(?:file|image)\s*:")
WIKI_SPACE_PATTERN: re.Pattern[str] = re.compile(r"\s+")
WIKI_MAX_TEMPLATE_DEPTH: int = 10

# Templates that are replaced by their content instead of being dropped.
WIKI_LIST_TEMPLATES: set[str] = {"hlist", "plainlist", "flatlist", "ubl", "unbulleted list", "bulleted list"}
WIKI_PASSTHROUGH_TEMPLATES: set[str] = {"nowrap", "nobr", "small", "big", "abbr"}
WIKI_CIRCA_TEMPLATES: set[str] = {"circa", "c.", "c", "ca", "ca."}
WIKI_CONVERT_TEMPLATES: set[str] = {"convert", "cvt"}
WIKI_LANG_TEMPLATES: set[str] = {"lang", "transl", "native name"}

# ---- infobox structure (Python re) ----
WIKI_INFOBOX_START_PATTERN: re.Pattern[str] = re.compile(r"(?i)\{\{\s*infobox[ _]+([^|{}\n]*)")
# One top-level piece of an infobox, already split on "|": "name = value" (the value may span lines).
WIKI_INFOBOX_PARAM_PATTERN: re.Pattern[str] = re.compile(r"(?s)^\s*([A-Za-z0-9_ \-]+?)\s*=(.*)$")

# ---- dates (Python re) ----
# {{birth date|1890|8|24|mf=y}}, {{Death date and age|1968|1|22|1890|8|24}}: the numbers are the date, named arguments are skipped.
WIKI_DATE_TEMPLATE_PATTERN: re.Pattern[str] = re.compile(r"(?i)\{\{\s*(?:birth|death|start|end)[ _-]*(?:date|year)[^|{}]*\|([^{}]*)\}\}")
WIKI_DATE_DMY_PATTERN: re.Pattern[str] = re.compile(r"(\d{1,2})\s+([A-Za-z]{3,9})\.?\s+(\d{1,4})")    # 3 December 1949
WIKI_DATE_MDY_PATTERN: re.Pattern[str] = re.compile(r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{1,4})")  # August 24, 1890
WIKI_DATE_MY_PATTERN: re.Pattern[str] = re.compile(r"([A-Za-z]{3,9})\.?\s+(\d{3,4})")                 # August 1890
WIKI_DATE_Y_PATTERN: re.Pattern[str] = re.compile(r"\b(\d{3,4})\b")                                    # 490
WIKI_DATE_CIRCA_PATTERN: re.Pattern[str] = re.compile(r"(?i)\b(?:c\.|ca\.?|circa|about|around)(?=\s|\d)")
WIKI_PARENTHESIS_PATTERN: re.Pattern[str] = re.compile(r"\([^)]*\)")                                  # (aged 47)
WIKI_DATE_BC_PATTERN: re.Pattern[str] = re.compile(r"(?i)\b(?:bc|bce)\b")
WIKI_MONTHS: dict[str, int] = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# ---- measurements (Python re) ----
WIKI_HEIGHT_CM_PATTERN: re.Pattern[str] = re.compile(r"(\d{2,3}(?:\.\d+)?)\s*cm\b")
WIKI_HEIGHT_M_PATTERN: re.Pattern[str] = re.compile(r"\b(\d(?:\.\d{1,2})?)\s*m\b")
WIKI_HEIGHT_FT_PATTERN: re.Pattern[str] = re.compile(r"(\d)\s*(?:ft|feet|foot|')\s*(?:(\d+(?:\.\d+)?)\s*(?:in|inches|\"))?")
WIKI_WEIGHT_KG_PATTERN: re.Pattern[str] = re.compile(r"(\d{2,3}(?:\.\d+)?)\s*kg\b")
WIKI_WEIGHT_LB_PATTERN: re.Pattern[str] = re.compile(r"(\d{2,3}(?:\.\d+)?)\s*(?:lb|lbs|pounds)\b")
WIKI_HEIGHT_RANGE_CM: tuple[int, int] = (100, 250)
WIKI_WEIGHT_RANGE_KG: tuple[int, int] = (30, 250)

# ---- medals in infoboxes (Python re) ----
# {{MedalGold | 1912 Stockholm | 100 m freestyle}}, {{Medal | Gold | 1912 Stockholm | 100 m freestyle}},
# {{MedalCompetition | Olympic Games}}, {{Medal|Competition|Olympic Games}}
WIKI_MEDAL_TEMPLATE_PATTERN: re.Pattern[str] = re.compile(r"(?is)\{\{\s*medal([a-z]*)\s*\|(.*?)\}\}")
WIKI_OLYMPIC_TEXT_PATTERN: re.Pattern[str] = re.compile(r"(?i)(?<![a-z])olympic")
WIKI_YOUTH_TEXT_PATTERN: re.Pattern[str] = re.compile(r"(?i)\byouth\b")
WIKI_MEDAL_KINDS: set[str] = {"gold", "silver", "bronze"}

# ---- categories (Python re) ----
WIKI_CATEGORY_BIRTH_PATTERN: re.Pattern[str] = re.compile(r"(?i)^(\d{1,4})\s+(bc\s+)?births$")
WIKI_CATEGORY_DEATH_PATTERN: re.Pattern[str] = re.compile(r"(?i)^(\d{1,4})\s+(bc\s+)?deaths$")
WIKI_CATEGORY_GAMES_PATTERN: re.Pattern[str] = re.compile(r"(?i)\bat the (\d{4}) (Summer|Winter) Olympics$")
WIKI_CATEGORY_MEDAL_TYPE_PATTERN: re.Pattern[str] = re.compile(r"(?i)^Olympic (gold|silver|bronze) medalists")
WIKI_CATEGORY_COUNTRY_PATTERN: re.Pattern[str] = re.compile(r"(?i)^Olympic .*? for (?:the )?(.+?)(?: in .*)?$")

# ---- join: Olympedia athletes <-> wikipedia people (stage 4) ----
WIKI_JOIN_PATH: str = os.path.join(DATA_DIR, "joined_parquet")

# Name normalisation (Python re): after NFKD and removal of the accents, everything that is not a-z0-9 is a space.
JOIN_NAME_NON_ALNUM_PATTERN: re.Pattern[str] = re.compile(r"[^a-z0-9]+")
# Letters that NFKD does not decompose.
JOIN_NAME_LETTER_MAP: dict[str, str] = {
    "ß": "ss", "æ": "ae", "œ": "oe", "ø": "o", "đ": "d", "ð": "d", "þ": "th", "ł": "l", "ı": "i",
}
# UTF-8 text that was decoded as Windows-1252 ("PyrÃ©nÃ©es", "â€œ") is repaired when it shows these.
JOIN_MOJIBAKE_PATTERN: re.Pattern[str] = re.compile(r"Ã.|â€")
# A trailing disambiguation "(swimmer)" of a wikipedia title. Java regex for Spark's regexp_replace.
JOIN_TITLE_SUFFIX_REGEX: str = r"\s*\([^)]*\)$"
# Olympedia born_date shapes (Java regex for Spark's rlike): a full date, and anything that starts with a year.
JOIN_FULL_DATE_REGEX: str = r"^\d{4}-\d{2}-\d{2}$"
JOIN_YEAR_REGEX: str = r"^\d{4}"

# Tolerances. An exact-id pair whose birth years are further apart than this is an `id_conflict` (the page cites
# another person's id) and is set aside. The other two decide when the sources are said to disagree.
JOIN_ID_YEAR_TOLERANCE: int = 1
JOIN_BIRTH_YEAR_TOLERANCE: int = 1
JOIN_HEIGHT_TOLERANCE_CM: float = 3.0
JOIN_WEIGHT_TOLERANCE_KG: float = 5.0

WIKI_MEASURE_TEMPLATES: set[str] = {"height", "weight"}
WIKI_FEET_UNITS: set[str] = {"ft", "feet", "foot"}
WIKI_INCH_UNITS: set[str] = {"in", "inch", "inches"}
WIKI_STONE_UNITS: set[str] = {"st", "stone"}
WIKI_POUND_UNITS: set[str] = {"lb", "lbs", "pound", "pounds"}
WIKI_NUMBER_PATTERN: re.Pattern[str] = re.compile(r"^\d+(?:\.\d+)?$")
WIKI_WEIGHT_ST_PATTERN: re.Pattern[str] = re.compile(r"(\d{1,2})\s*(?:st|stone)\b\s*(?:(\d{1,2}(?:\.\d+)?)\s*(?:lb|lbs|pounds)\b)?")

# ---- olympedia extraction with Spark (extract-spark) ----
OLYMPEDIA_ATHLETES_PARQUET_PATH: str = os.path.join(DATA_DIR, "extracted_parquet", "athletes")
OLYMPEDIA_RESULTS_PARQUET_PATH: str = os.path.join(DATA_DIR, "extracted_parquet", "results")
# The raw pages are about 124 MB in few partitions; they are split so that every core gets pages to parse.
OLYMPEDIA_SPARK_PARTITIONS: int = 64
# Athlete id from the path of a stored page ("file:/.../raw/athletes/21846.html" -> 21846). Java regex for Spark's regexp_extract.
OLYMPEDIA_FILE_ID_REGEX: str = r"([^/\\]+)\.html$"