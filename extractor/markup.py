import html as html_lib
from dataclasses import dataclass

from constants.extractor import MAX_COLSPAN
from crawler.links import body_of, clean_anchor_text
from regexes.crawler import TAG_PATTERN
from regexes.extractor import (
    CELL_PATTERN,
    COLSPAN_PATTERN,
    COMMENT_PATTERN,
    H2_PATTERN,
    LIST_ITEM_PATTERN,
    PARAGRAPH_PATTERN,
    ROW_PATTERN,
    SCRIPT_STYLE_PATTERN,
    TABLE_PATTERN,
)


@dataclass
class Cell:
    tag: str
    raw: str
    text: str


def prepare_body(page_html: str) -> str:
    """body_of() minus comments, scripts and styles."""
    body = body_of(page_html)
    body = COMMENT_PATTERN.sub("", body)
    return SCRIPT_STYLE_PATTERN.sub("", body)


def text_of(fragment: str) -> str:
    return clean_anchor_text(fragment)


def lines_of(fragment: str) -> list[str]:
    """Visible text, every tag boundary becomes a line break."""
    unescaped = html_lib.unescape(TAG_PATTERN.sub("\n", fragment))
    lines: list[str] = []

    for raw_line in unescaped.split("\n"):
        line = " ".join(raw_line.split())

        if line != "":
            lines.append(line)

    return lines


def split_sections(body: str) -> dict[str, str]:
    """Lower-cased <h2> title -> html up to the next <h2>, first occurrence wins."""
    matches = list(H2_PATTERN.finditer(body))
    sections: dict[str, str] = {}

    for index, match in enumerate(matches):
        title = text_of(match.group(1)).lower()

        if index + 1 < len(matches):
            end = matches[index + 1].start()
        else:
            end = len(body)

        if title not in sections:
            sections[title] = body[match.end() : end]

    return sections


def split_tables(fragment: str) -> list[str]:
    return TABLE_PATTERN.findall(fragment)


def split_rows(fragment: str) -> list[str]:
    return ROW_PATTERN.findall(fragment)


def split_cells(row_html: str) -> list[Cell]:
    """colspan is padded with empty cells to keep column indices aligned."""
    cells: list[Cell] = []

    for match in CELL_PATTERN.finditer(row_html):
        tag = match.group(1).lower()
        raw = match.group(3)
        cells.append(Cell(tag, raw, text_of(raw)))

        span = COLSPAN_PATTERN.search(match.group(2))

        if span is None:
            continue

        for _ in range(min(int(span.group(1)), MAX_COLSPAN) - 1):
            cells.append(Cell(tag, "", ""))

    return cells


def paragraphs_of(fragment: str) -> list[str]:
    found = [text_of(paragraph) for paragraph in PARAGRAPH_PATTERN.findall(fragment)]
    return [paragraph for paragraph in found if paragraph != ""]


def list_items_of(fragment: str) -> list[str]:
    found = [text_of(item) for item in LIST_ITEM_PATTERN.findall(fragment)]
    return [item for item in found if item != ""]