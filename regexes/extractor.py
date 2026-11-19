import re

# ---- page structure ----
COMMENT_PATTERN: re.Pattern[str] = re.compile(r"(?s)<!--.*?-->")
SCRIPT_STYLE_PATTERN: re.Pattern[str] = re.compile(r"(?is)<(script|style)\b.*?</\1>")
H2_PATTERN: re.Pattern[str] = re.compile(r"(?is)<h2\b[^>]*>(.*?)</h2>")
TABLE_PATTERN: re.Pattern[str] = re.compile(r"(?is)<table\b[^>]*>(.*?)</table>")
ROW_PATTERN: re.Pattern[str] = re.compile(r"(?is)<tr\b[^>]*>(.*?)</tr>")
CELL_PATTERN: re.Pattern[str] = re.compile(r"(?is)<(t[hd])\b([^>]*)>(.*?)</\1>")
COLSPAN_PATTERN: re.Pattern[str] = re.compile(r"(?i)colspan\s*=\s*[\"']?(\d+)")
PARAGRAPH_PATTERN: re.Pattern[str] = re.compile(r"(?is)<p\b[^>]*>(.*?)</p>")
LIST_ITEM_PATTERN: re.Pattern[str] = re.compile(r"(?is)<li\b[^>]*>(.*?)</li>")
ANCHOR_PATTERN: re.Pattern[str] = re.compile(r"(?is)<a\b[^>]*>(.*?)</a>")
COUNTRY_HREF_PATTERN: re.Pattern[str] = re.compile(r'href="/countries/([A-Za-z0-9]{2,3})"')

# ---- values ----
MEDAL_COUNT_PATTERN: re.Pattern[str] = re.compile(
    r"(?is)<t[hd]\b[^>]*>(?:\s|<[^>]+>)*(Gold|Silver|Bronze|Total)(?:\s|<[^>]+>)*</t[hd]>"
    r"\s*<t[hd]\b[^>]*>\s*(\d+)\s*</t[hd]>"
)
MEDAL_TEXT_PATTERN: re.Pattern[str] = re.compile(r"^(Gold|Silver|Bronze)$")

HEIGHT_PATTERN: re.Pattern[str] = re.compile(r"(\d+)\s*cm")
WEIGHT_PATTERN: re.Pattern[str] = re.compile(r"(\d+)\s*kg")
AGED_PATTERN: re.Pattern[str] = re.compile(r"\s*\(aged\s+[^)]*\)")
TRAILING_NOC_PATTERN: re.Pattern[str] = re.compile(r"^(?P<place>.*?)\s*\((?P<noc>[A-Z]{3})\)\s*$")
DATE_DMY_PATTERN: re.Pattern[str] = re.compile(r"^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$")
DATE_MY_PATTERN: re.Pattern[str] = re.compile(r"^([A-Za-z]+)\s+(\d{4})$")
DATE_Y_PATTERN: re.Pattern[str] = re.compile(r"^(\d{4})$")
PERSONAL_BEST_PATTERN: re.Pattern[str] = re.compile(r"(?im)^\s*Personal Bests?\s*:\s*(.+?)\s*$")

# ---- results table ----
GAMES_PATTERN: re.Pattern[str] = re.compile(r"^(\d{4})\s+(Summer|Winter|Intercalated)\b")       # 1980 Summer Olympics
EVENT_STATUS_PATTERN: re.Pattern[str] = re.compile(r"\s*\([^()]*\)\s*$")                         # Basketball, Women (Olympic)
DISCIPLINE_PATTERN: re.Pattern[str] = re.compile(r"^(?P<discipline>.*?)\s*\((?P<sport>[^()]*)\)\s*$")  # Diving (Aquatics)

# ---- biography mining ----
# A rule only flags a sentence; the whole sentence is kept.
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

# ---- spark ----
# "file:/.../raw/athletes/21846.html" -> 21846
OLYMPEDIA_FILE_ID_REGEX: str = r"([^/\\]+)\.html$"
