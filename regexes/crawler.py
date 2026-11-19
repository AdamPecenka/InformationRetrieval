import re

from constants.common import BASE_URL

URL_WHITELIST: re.Pattern[str] = re.compile(
    "^" + re.escape(BASE_URL) + r"/(athletes/\d+|editions(/\d+(/medal)?)?|countries(/[A-Z]{3})?)$"
)
ATHLETE_URL_PATTERN: re.Pattern[str] = re.compile("^" + re.escape(BASE_URL) + r"/athletes/(\d+)$")

# An athlete page is stored when it has both.
BIO_HEADING_PATTERN: re.Pattern[str] = re.compile(r"<h2>\s*Biography\s*</h2>")
MEDAL_SPAN_PATTERN: re.Pattern[str] = re.compile(r'<span class="(Gold|Silver|Bronze)">')

# Lookbehind keeps "data-href" out.
LINK_PATTERN: re.Pattern[str] = re.compile(
    r"<a\s[^>]*?(?<![\w-])href\s*=\s*(?:\"([^\"]*)\"|'([^']*)')[^>]*>(.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)
TAG_PATTERN: re.Pattern[str] = re.compile(r"<[^>]+>")
