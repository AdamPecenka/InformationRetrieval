import re

# ==== spark (Java regex strings) ====

WIKI_BIO_REGEX: str = r"(?i)\[\[category:\d{1,4}( bc)? births|\|\s*birth_date\s*="

# ---- relevance filter (stage 2) ----
# A page is kept when ANY flag fires, so these lean generous: an extra page costs disk, a missed one breaks the join.
# Category words are delimited by "not a letter" instead of \b: \b treats "_" as a word char ("Year_of_birth_missing"),
# and the lookarounds keep "Childbirth", "Birth control", "Death metal" out.
_NOT_AFTER_LETTER: str = r"(?<![a-z])"
_NOT_BEFORE_LETTER: str = r"(?![a-z])"
_CATEGORY_OPEN: str = r"\[\[\s*category\s*:[^\]\n]*"

# "1986 births", "Deaths from cancer in Texas", "384 BC births", "Year of birth missing", "Living people".
WIKI_PERSON_CATEGORY_REGEX: str = (
    r"(?i)" + _CATEGORY_OPEN + r"(?:"
    + _NOT_AFTER_LETTER + r"(?:births|deaths|living[ _]people)" + _NOT_BEFORE_LETTER
    + r"|" + _NOT_AFTER_LETTER + r"(?:year|date)[ _]of[ _](?:birth|death)" + _NOT_BEFORE_LETTER
    + r")"
)

# Fallback for pages without a person category: "| birth_date =", "| born =", "{{birth date|...}}", "{{bda|...}}".
WIKI_PERSON_INFOBOX_REGEX: str = (
    r"(?i)\|\s*(?:birth[ _]?date|date[ _]?of[ _]?birth|birth[ _]?year|born)\s*="
    r"|\{\{\s*(?:birth[ _-]?date|birth[ _-]?year|birth[ _-]based|bda|b-da|dob)\b"
)

# "Germany at the 1976 Summer Olympics", "1906 Intercalated Games". Paralympics left out on purpose.
WIKI_OLYMPIC_TITLE_REGEX: str = r"(?i)\bolympic|intercalated games"

# "Competitors at the 1976 Summer Olympics", "Olympians ...", "Ancient Olympic competitors".
WIKI_OLYMPIC_CATEGORY_REGEX: str = (
    r"(?i)" + _CATEGORY_OPEN
    + _NOT_AFTER_LETTER + r"(?:olympics?|olympians?|intercalated[ _]games)" + _NOT_BEFORE_LETTER
)

# "{{MedalCompetition | [[Olympic Games]] ...}}". Guess at infobox medal markup; wiki-filter reports its only-hits.
WIKI_OLYMPIC_MEDAL_REGEX: str = r"(?i)\{\{\s*medal[^}\n]*" + _NOT_AFTER_LETTER + r"olympic"

# External link, reference or {{Olympedia}} template.
WIKI_OLYMPEDIA_LINK_REGEX: str = r"(?i)olympedia\.org|\{\{\s*olympedia" + _NOT_BEFORE_LETTER

# Olympedia athlete ids, one group each, used with regexp_extract_all (a page may cite several).
WIKI_OLYMPEDIA_URL_ID_REGEX: str = r"(?i)olympedia\.org/athletes/(\d+)"
# First number in the template ("|91889", "|id=91889", "|athlete|91889"). Bare {{Olympedia}} (Wikidata id) gives none.
WIKI_OLYMPEDIA_TEMPLATE_ID_REGEX: str = r"(?i)\{\{\s*olympedia" + _NOT_BEFORE_LETTER + r"[^}\n]*?\b(\d+)\b"

# ---- attribute extraction (stage 3) ----
WIKI_CATEGORY_NAME_REGEX: str = r"(?i)\[\[\s*category\s*:\s*([^\]|\n]+)"

# ---- audit ----
WIKI_OLYMPIC_MENTION_REGEX: str = r"(?i)olymp"
WIKI_SNIPPET_REGEX: str = r"(?is)(.{0,70}olymp.{0,70})"
WIKI_WHITESPACE_REGEX: str = r"\s+"


# ==== python ====

# ---- markup clean-up ----
WIKI_COMMENT_PATTERN: re.Pattern[str] = re.compile(r"(?s)<!--.*?-->")
WIKI_REF_PATTERN: re.Pattern[str] = re.compile(r"(?is)<ref\b[^>]*?/>|<ref\b[^>]*>.*?</ref>")
WIKI_BREAK_PATTERN: re.Pattern[str] = re.compile(r"(?i)<br\s*/?>")
WIKI_TAG_PATTERN: re.Pattern[str] = re.compile(r"<[^>]+>")
WIKI_LINK_PATTERN: re.Pattern[str] = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]")      # [[a|b]], [[b]] -> b
WIKI_EXTERNAL_LINK_PATTERN: re.Pattern[str] = re.compile(r"\[https?://\S+\s*([^\]]*)\]")  # [http://x text] -> text
WIKI_INNER_TEMPLATE_PATTERN: re.Pattern[str] = re.compile(r"\{\{([^{}]*)\}\}")           # innermost template
WIKI_BULLET_PATTERN: re.Pattern[str] = re.compile(r"\s*\n\s*\*\s*")
WIKI_EMPTY_PARENTHESES_PATTERN: re.Pattern[str] = re.compile(r"\(\s*[;,\u2013\-]?\s*\)")  # left by a dropped date template
WIKI_SECTION_PATTERN: re.Pattern[str] = re.compile(r"(?m)^==(?!=)\s*(.+?)\s*==\s*$")       # level 2 only
WIKI_HEADING_MARKUP_PATTERN: re.Pattern[str] = re.compile(r"(?m)^(=+)\s*(.+?)\s*\1\s*$")  # any level
WIKI_TABLE_PATTERN: re.Pattern[str] = re.compile(r"(?s)\{\|.*?\|\}")
WIKI_WANTED_SECTION_PATTERN: re.Pattern[str] = re.compile(
    r"(?i)\b(?:biography|early (?:life|years)|childhood|background|education|career|olympics?|personal life|later (?:life|years)|life|death|achievements?)\b"
)
WIKI_STRAY_OPENING_PATTERN: re.Pattern[str] = re.compile(r"\(\s*[;,]\s*")          # "(; Greek" -> "(Greek"
WIKI_STRAY_SEPARATOR_PATTERN: re.Pattern[str] = re.compile(r"([;,])\s*[;,]\s*")  # ", ;" -> ","
WIKI_LEAD_IMAGE_PATTERN: re.Pattern[str] = re.compile(r"(?i)^\[\[\s*(?:file|image)\s*:")
WIKI_SPACE_PATTERN: re.Pattern[str] = re.compile(r"\s+")

# ---- infobox ----
WIKI_INFOBOX_START_PATTERN: re.Pattern[str] = re.compile(r"(?i)\{\{\s*infobox[ _]+([^|{}\n]*)")
# One "|"-separated piece: "name = value", value may span lines.
WIKI_INFOBOX_PARAM_PATTERN: re.Pattern[str] = re.compile(r"(?s)^\s*([A-Za-z0-9_ \-]+?)\s*=(.*)$")

# ---- dates ----
# {{birth date|1890|8|24|mf=y}}, {{Death date and age|1968|1|22|1890|8|24}}
WIKI_DATE_TEMPLATE_PATTERN: re.Pattern[str] = re.compile(r"(?i)\{\{\s*(?:birth|death|start|end)[ _-]*(?:date|year)[^|{}]*\|([^{}]*)\}\}")
WIKI_DATE_DMY_PATTERN: re.Pattern[str] = re.compile(r"(\d{1,2})\s+([A-Za-z]{3,9})\.?\s+(\d{1,4})")    # 3 December 1949
WIKI_DATE_MDY_PATTERN: re.Pattern[str] = re.compile(r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{1,4})")  # August 24, 1890
WIKI_DATE_MY_PATTERN: re.Pattern[str] = re.compile(r"([A-Za-z]{3,9})\.?\s+(\d{3,4})")                 # August 1890
WIKI_DATE_Y_PATTERN: re.Pattern[str] = re.compile(r"\b(\d{3,4})\b")                                    # 490
WIKI_DATE_CIRCA_PATTERN: re.Pattern[str] = re.compile(r"(?i)\b(?:c\.|ca\.?|circa|about|around)(?=\s|\d)")
WIKI_PARENTHESIS_PATTERN: re.Pattern[str] = re.compile(r"\([^)]*\)")                                  # (aged 47)
WIKI_DATE_BC_PATTERN: re.Pattern[str] = re.compile(r"(?i)\b(?:bc|bce)\b")

# ---- measurements ----
WIKI_NUMBER_PATTERN: re.Pattern[str] = re.compile(r"^\d+(?:\.\d+)?$")
WIKI_HEIGHT_CM_PATTERN: re.Pattern[str] = re.compile(r"(\d{2,3}(?:\.\d+)?)\s*cm\b")
WIKI_HEIGHT_M_PATTERN: re.Pattern[str] = re.compile(r"\b(\d(?:\.\d{1,2})?)\s*m\b")
WIKI_HEIGHT_FT_PATTERN: re.Pattern[str] = re.compile(r"(\d)\s*(?:ft|feet|foot|')\s*(?:(\d+(?:\.\d+)?)\s*(?:in|inches|\"))?")
WIKI_WEIGHT_KG_PATTERN: re.Pattern[str] = re.compile(r"(\d{2,3}(?:\.\d+)?)\s*kg\b")
WIKI_WEIGHT_ST_PATTERN: re.Pattern[str] = re.compile(r"(\d{1,2})\s*(?:st|stone)\b\s*(?:(\d{1,2}(?:\.\d+)?)\s*(?:lb|lbs|pounds)\b)?")
WIKI_WEIGHT_LB_PATTERN: re.Pattern[str] = re.compile(r"(\d{2,3}(?:\.\d+)?)\s*(?:lb|lbs|pounds)\b")

# ---- medals ----
# {{MedalGold | 1912 Stockholm | 100 m}}, {{Medal | Gold | ...}}, {{MedalCompetition | Olympic Games}}, {{Medal|Competition|...}}
WIKI_MEDAL_TEMPLATE_PATTERN: re.Pattern[str] = re.compile(r"(?is)\{\{\s*medal([a-z]*)\s*\|(.*?)\}\}")
WIKI_OLYMPIC_TEXT_PATTERN: re.Pattern[str] = re.compile(r"(?i)(?<![a-z])olympic")
WIKI_YOUTH_TEXT_PATTERN: re.Pattern[str] = re.compile(r"(?i)\byouth\b")

# ---- categories ----
WIKI_CATEGORY_BIRTH_PATTERN: re.Pattern[str] = re.compile(r"(?i)^(\d{1,4})\s+(bc\s+)?births$")
WIKI_CATEGORY_DEATH_PATTERN: re.Pattern[str] = re.compile(r"(?i)^(\d{1,4})\s+(bc\s+)?deaths$")
WIKI_CATEGORY_GAMES_PATTERN: re.Pattern[str] = re.compile(r"(?i)\bat the (\d{4}) (Summer|Winter) Olympics$")
WIKI_CATEGORY_MEDAL_TYPE_PATTERN: re.Pattern[str] = re.compile(r"(?i)^Olympic (gold|silver|bronze) medalists")
WIKI_CATEGORY_COUNTRY_PATTERN: re.Pattern[str] = re.compile(r"(?i)^Olympic .*? for (?:the )?(.+?)(?: in .*)?$")

# ---- sample ----
WIKI_FILE_NAME_UNSAFE_PATTERN: re.Pattern[str] = re.compile(r"[^A-Za-z0-9]+")
