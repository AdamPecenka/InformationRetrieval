from constants.common import LIST_SEPARATOR
from constants.extractor import BIODATA_LABELS, BULLET, MONTHS
from extractor.markup import lines_of, split_cells, split_rows, text_of
from regexes.extractor import (
    AGED_PATTERN,
    ANCHOR_PATTERN,
    COUNTRY_HREF_PATTERN,
    DATE_DMY_PATTERN,
    DATE_MY_PATTERN,
    DATE_Y_PATTERN,
    HEIGHT_PATTERN,
    MEDAL_COUNT_PATTERN,
    PERSONAL_BEST_PATTERN,
    TRAILING_NOC_PATTERN,
    WEIGHT_PATTERN,
)


def split_name(raw: str) -> tuple[str, str, str]:
    """'Sarah Rozanne•Osvath' -> ('Sarah Rozanne Osvath', 'Sarah Rozanne', 'Osvath')."""
    if BULLET not in raw:
        return raw.strip(), "", raw.strip()

    given, _, family = raw.partition(BULLET)
    given = given.strip()
    family = family.strip()
    return f"{given} {family}".strip(), given, family


def parse_date_iso(raw: str) -> str:
    """-> YYYY-MM-DD / YYYY-MM / YYYY, anything else ("c. 1900") as is."""
    raw = raw.strip()

    match = DATE_DMY_PATTERN.match(raw)
    if match is not None:
        month = MONTHS.get(match.group(2).lower())
        if month is None:
            return raw
        return f"{match.group(3)}-{month:02d}-{int(match.group(1)):02d}"

    match = DATE_MY_PATTERN.match(raw)
    if match is not None:
        month = MONTHS.get(match.group(1).lower())
        if month is None:
            return raw
        return f"{match.group(2)}-{month:02d}"

    match = DATE_Y_PATTERN.match(raw)
    if match is not None:
        return match.group(1)

    return raw


def parse_date_place(raw: str) -> tuple[str, str, str]:
    """'13 August 2021 (aged 23 ...) in Mount Elgon, Bungoma (KEN)' -> (iso_date, place, country_code)."""
    text = AGED_PATTERN.sub("", raw).strip()
    date_part, separator, place_part = text.partition(" in ")

    if separator == "":
        return parse_date_iso(text), "", ""

    place = place_part.strip()
    country = ""
    match = TRAILING_NOC_PATTERN.match(place)

    if match is not None:
        place = match.group("place").strip()
        country = match.group("noc")

    return parse_date_iso(date_part), place, country


def _join(items: list[str]) -> str:
    return LIST_SEPARATOR.join(item for item in items if item != "")


def _comma_list(raw: str) -> str:
    return _join([part.strip() for part in raw.split(",")])


def _bullet_list(raw: str) -> str:
    return _join([part.strip() for part in raw.split(BULLET)])


def _link_texts(raw_html: str) -> list[str]:
    """Link texts of a cell, or its plain text if it has no links."""
    texts = [text_of(anchor) for anchor in ANCHOR_PATTERN.findall(raw_html)]
    texts = [text for text in texts if text != ""]

    if texts:
        return texts

    plain = text_of(raw_html)

    if plain == "":
        return []

    return [plain]


def _labelled_rows(section_html: str) -> dict[str, str]:
    """BIODATA_LABELS label -> raw html of its value cell."""
    found: dict[str, str] = {}

    for row_html in split_rows(section_html):
        cells = split_cells(row_html)

        if len(cells) < 2:
            continue

        label = cells[0].text

        if label in BIODATA_LABELS and label not in found:
            found[label] = cells[1].raw

    return found


def parse_medal_counts(section_html: str) -> dict[str, str]:
    """Medal box counts (first column: OG, or YOG for youth-only athletes)."""
    counts: dict[str, str] = {}

    for label, number in MEDAL_COUNT_PATTERN.findall(section_html):
        key = label.lower()

        if key not in counts:
            counts[key] = number

    return counts


def parse_personal_bests(*fragments: str) -> str:
    found: list[str] = []

    for fragment in fragments:
        for line in lines_of(fragment):
            match = PERSONAL_BEST_PATTERN.match(line)

            if match is not None:
                found.append(match.group(1))

    return LIST_SEPARATOR.join(found)


def parse_biodata(section_html: str) -> dict[str, str]:
    """'Biographical information' table, missing rows -> ""."""
    rows = _labelled_rows(section_html)

    def text(label: str) -> str:
        if label in rows:
            return text_of(rows[label])
        return ""

    def codes(label: str) -> list[str]:
        if label in rows:
            return COUNTRY_HREF_PATTERN.findall(rows[label])
        return []

    def names(label: str) -> list[str]:
        if label in rows:
            return _link_texts(rows[label])
        return []

    fields: dict[str, str] = {}

    full_name, given, family = split_name(text("Full name"))
    fields["full_name"] = full_name
    fields["given_names"] = given
    fields["family_name"] = family
    fields["used_name"] = split_name(text("Used name"))[0]
    fields["other_names"] = _comma_list(text("Other names"))
    fields["original_name"] = text("Original name")
    fields["nickname"] = text("Nickname")
    fields["sex"] = text("Sex")
    fields["roles"] = _bullet_list(text("Roles"))

    born_date, born_place, born_country = parse_date_place(text("Born"))
    fields["born_date"] = born_date
    fields["born_place"] = born_place
    fields["born_country"] = born_country

    died_date, died_place, died_country = parse_date_place(text("Died"))
    fields["died_date"] = died_date
    fields["died_place"] = died_place
    fields["died_country"] = died_country

    measurements = text("Measurements")
    height = HEIGHT_PATTERN.search(measurements)
    weight = WEIGHT_PATTERN.search(measurements)
    fields["height_cm"] = ""
    fields["weight_kg"] = ""

    if height is not None:
        fields["height_cm"] = height.group(1)

    if weight is not None:
        fields["weight_kg"] = weight.group(1)

    fields["affiliations"] = _join(names("Affiliations"))
    fields["noc_codes"] = _join(codes("NOC"))
    fields["noc_names"] = _join(names("NOC"))
    fields["nationality_codes"] = _join(codes("Nationality"))
    fields["nationality_names"] = _join(names("Nationality"))

    return fields