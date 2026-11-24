import re

# After NFKD + accent removal, anything outside a-z0-9 becomes a space.
JOIN_NAME_NON_ALNUM_PATTERN: re.Pattern[str] = re.compile(r"[^a-z0-9]+")
# UTF-8 decoded as Windows-1252: "PyrÃ©nÃ©es", "â€œ".
JOIN_MOJIBAKE_PATTERN: re.Pattern[str] = re.compile(r"Ã.|â€")

# ---- spark ----
JOIN_TITLE_SUFFIX_REGEX: str = r"\s*\([^)]*\)$"   # "John Davis (swimmer)" -> "John Davis"
JOIN_FULL_DATE_REGEX: str = r"^\d{4}-\d{2}-\d{2}$"
JOIN_YEAR_REGEX: str = r"^\d{4}"

# Same suffix rule for the Lucene index (container, plain re).
JOIN_TITLE_SUFFIX_PATTERN: re.Pattern[str] = re.compile(JOIN_TITLE_SUFFIX_REGEX)
