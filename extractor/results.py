import constants
from extractor.markup import Cell, split_cells, split_rows, split_tables


class _Columns:
    """Header positions of a table. -1 means the column is absent."""

    def __init__(self, header: list[str]) -> None:
        self.games = self._find(header, "games")
        self.event = self._find(header, "event")
        self.noc_team = self._find(header, "noc")
        self.role = self._find(header, "role")
        self.position = self._find(header, "pos")
        self.medal = self._find(header, "medal")

    @staticmethod
    def _find(header: list[str], needle: str) -> int:
        for index, title in enumerate(header):
            if needle in title.lower():
                return index
        return -1


def _cell_text(cells: list[Cell], column: int, offset: int = 0) -> str:
    """Text of the cell under header column `column` ('' when the row has no such cell)."""
    if column < 0:
        return ""

    position = column - offset

    if position < 0 or position >= len(cells):
        return ""

    return cells[position].text


def _find_results_table(section_html: str) -> list[str] | None:
    for table_html in split_tables(section_html):
        rows = split_rows(table_html)

        if not rows:
            continue

        header = " ".join(cell.text for cell in split_cells(rows[0])).lower()

        if "games" in header and "event" in header:
            return rows

    return None


def parse_results(section_html: str, athlete_id: str) -> list[dict[str, str]]:
    """One dict (see constants.RESULT_COLUMNS) per event row.

    Layout: a games row ("1976 Summer Olympics | Handball | FRG | ...") sets games and
    discipline, the event rows below it start with an empty Games cell.
    """
    rows = _find_results_table(section_html)

    if rows is None:
        return []

    columns = _Columns([cell.text for cell in split_cells(rows[0])])

    if columns.event < 0:
        return []

    games = ""
    year = ""
    season = ""
    discipline = ""
    sport = ""
    results: list[dict[str, str]] = []

    for row_html in rows[1:]:
        cells = split_cells(row_html)

        if not cells:
            continue

        if all(cell.tag == "th" for cell in cells):
            continue

        games_match = constants.GAMES_PATTERN.match(cells[0].text)

        if games_match is not None:
            games = cells[0].text
            year = games_match.group(1)
            season = games_match.group(2)

            discipline_text = _cell_text(cells, columns.event)
            discipline_match = constants.DISCIPLINE_PATTERN.match(discipline_text)

            discipline = discipline_text
            sport = discipline_text

            if discipline_match is not None:
                discipline = discipline_match.group("discipline")
                sport = discipline_match.group("sport")

            continue

        event_text = _cell_text(cells, columns.event)

        if event_text == "":
            continue

        medal = _cell_text(cells, columns.medal)

        if constants.MEDAL_TEXT_PATTERN.match(medal) is None:
            medal = ""

        results.append(
            {
                "athlete_id": athlete_id,
                "games": games,
                "year": year,
                "season": season,
                "sport": sport,
                "discipline": discipline,
                "event": constants.EVENT_STATUS_PATTERN.sub("", event_text).strip(),
                "team": _cell_text(cells, columns.noc_team),
                "position": _cell_text(cells, columns.position),
                "medal": medal,
            }
        )

    return results


def parse_other_participations(section_html: str) -> list[str]:
    """Rows of the 'Other participations' table (Games | Role | NOC | As) as 'games: role'.

    Holds the non-competing roles: flag-bearer, torch-bearer, oath taker, ...
    """
    for table_html in split_tables(section_html):
        rows = split_rows(table_html)

        if not rows:
            continue

        header = [cell.text for cell in split_cells(rows[0])]
        columns = _Columns(header)

        if columns.role < 0:
            continue

        found: list[str] = []
        games = ""

        for row_html in rows[1:]:
            cells = split_cells(row_html)

            if not cells or all(cell.tag == "th" for cell in cells):
                continue

            # A row can lack the leading Games cell (rowspan of the row above).
            offset = max(len(header) - len(cells), 0)
            row_games = _cell_text(cells, columns.games, offset)
            role = _cell_text(cells, columns.role, offset)

            if row_games != "":
                games = row_games

            if role != "":
                found.append(f"{games}: {role}")

        return found

    return []