import html as html_lib
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

import constants

# <a ... href="..." ...>text</a>. The lookbehind stops "data-href" from matching.
_ANCHOR_PATTERN: re.Pattern[str] = re.compile(
    r"<a\s[^>]*?(?<![\w-])href\s*=\s*(?:\"([^\"]*)\"|'([^']*)')[^>]*>(.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)
_TAG_PATTERN: re.Pattern[str] = re.compile(r"<[^>]+>")


def body_of(page_html: str) -> str:
    """Everything before </body>.

    On Olympedia the footer sits after </body> and holds a random "Did you
    know?" fact that links to unrelated athletes, so it is cut off. The nav bar
    stays in; the only nav links that pass the whitelist are /editions and
    /countries, which is what a crawl started at the base URL needs.
    """
    index = page_html.find("</body>")

    if index == -1:
        return page_html

    return page_html[:index]


def clean_anchor_text(raw: str) -> str:
    """Strip tags, decode entities, collapse whitespace."""
    without_tags = _TAG_PATTERN.sub("", raw)
    unescaped = html_lib.unescape(without_tags)
    return " ".join(unescaped.split())


def normalize_url(href: str, base_url: str) -> str | None:
    cleaned = html_lib.unescape(href).strip()

    if cleaned == "":
        return None

    absolute = urljoin(base_url, cleaned)
    parts = urlsplit(absolute)

    if parts.scheme not in ("http", "https"):
        return None

    path = parts.path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    return urlunsplit((parts.scheme, parts.netloc.lower(), path, parts.query, ""))


def is_whitelisted(url: str) -> bool:
    return constants.URL_WHITELIST.match(url) is not None


def extract_links(page_html: str, base_url: str) -> list[tuple[str, str]]:
    own_url = normalize_url(base_url, base_url)
    found: dict[str, str] = {}

    for match in _ANCHOR_PATTERN.finditer(body_of(page_html)):
        href = match.group(1)

        if href is None:
            href = match.group(2)

        url = normalize_url(href, base_url)

        if url is None:
            continue

        if url == own_url:
            continue

        if not is_whitelisted(url):
            continue

        text = clean_anchor_text(match.group(3))
        existing = found.get(url)

        if existing is None:
            found[url] = text
        elif existing == "" and text != "":
            found[url] = text

    return list(found.items())


def athlete_id(url: str) -> str | None:
    match = constants.ATHLETE_URL_PATTERN.match(url)
    if match is None:
        return None
    return match.group(1)


def is_athlete_url(url: str) -> bool:
    return athlete_id(url) is not None


def athlete_flags(page_html: str) -> tuple[bool, bool]:
    body = body_of(page_html)
    has_bio = constants.BIO_HEADING_PATTERN.search(body) is not None
    has_medal = constants.MEDAL_SPAN_PATTERN.search(body) is not None
    return has_bio, has_medal
