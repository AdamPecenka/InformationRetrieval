import html as html_lib
from dataclasses import dataclass

import constants
from crawler.links import body_of, clean_anchor_text


@dataclass
class Cell:
    tag: str
    raw: str
    text: str


def prepare_body(page_html: str) -> str:
    """Page up to </body> (the same cut the crawler uses) without comments, scripts and styles."""
    body = body_of(page_html)
    body = constants.COMMENT_PATTERN.sub("", body)
    return constants.SCRIPT_STYLE_PATTERN.sub("", body)


def text_of(fragment: str) -> str:
    return clean_anchor_text(fragment)


def lines_of(fragment: str) -> list[str]:
    """Visible text, every tag boundary becomes a line break."""
    unescaped = html_lib.unescape(constants.TAG_PATTERN.sub("\n", fragment))
    lines: list[str] = []

    for raw_line in unescaped.split("\n"):
        line = " ".join(raw_line.split())

        if line != "":
            lines.append(line)

    return lines


def split_sections(body: str) -> dict[str, str]:
    """Lower-cased <h2> title -> html up to the next <h2>. The first occurrence of a title wins."""
    matches = list(constants.H2_PATTERN.finditer(body))
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
    return constants.TABLE_PATTERN.findall(fragment)


def split_rows(fragment: str) -> list[str]:
    return constants.ROW_PATTERN.findall(fragment)


def split_cells(row_html: str) -> list[Cell]:
    """Cells of one row. A colspan > 1 is padded with empty cells so column indices stay aligned."""
    cells: list[Cell] = []

    for match in constants.CELL_PATTERN.finditer(row_html):
        tag = match.group(1).lower()
        raw = match.group(3)
        cells.append(Cell(tag, raw, text_of(raw)))

        span = constants.COLSPAN_PATTERN.search(match.group(2))

        if span is None:
            continue

        for _ in range(min(int(span.group(1)), constants.MAX_COLSPAN) - 1):
            cells.append(Cell(tag, "", ""))

    return cells


def paragraphs_of(fragment: str) -> list[str]:
    found = [text_of(paragraph) for paragraph in constants.PARAGRAPH_PATTERN.findall(fragment)]
    return [paragraph for paragraph in found if paragraph != ""]


def list_items_of(fragment: str) -> list[str]:
    found = [text_of(item) for item in constants.LIST_ITEM_PATTERN.findall(fragment)]
    return [item for item in found if item != ""]