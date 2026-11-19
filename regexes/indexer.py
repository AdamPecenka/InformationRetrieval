import re

TOKEN_PATTERN: re.Pattern[str] = re.compile(r"[^\W_]+")
