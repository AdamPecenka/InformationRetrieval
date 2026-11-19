"""Person attributes from the head of a wikitext article. Plain Python, used as the UDF body in wiki/extract.py."""
import html
from typing import Optional

from constants.wiki import (
    WIKI_BODY_MAX_CHARS,
    WIKI_CIRCA_TEMPLATES,
    WIKI_CONVERT_TEMPLATES,
    WIKI_FEET_UNITS,
    WIKI_HEIGHT_RANGE_CM,
    WIKI_INCH_UNITS,
    WIKI_LANG_TEMPLATES,
    WIKI_LEAD_MAX_CHARS,
    WIKI_LIST_TEMPLATES,
    WIKI_MAX_TEMPLATE_DEPTH,
    WIKI_MEASURE_TEMPLATES,
    WIKI_MEDAL_KINDS,
    WIKI_MONTHS,
    WIKI_PASSTHROUGH_TEMPLATES,
    WIKI_POUND_UNITS,
    WIKI_SECTION_MAX_CHARS,
    WIKI_STONE_UNITS,
    WIKI_WEIGHT_RANGE_KG,
)
from regexes.wiki import (
    WIKI_BREAK_PATTERN,
    WIKI_BULLET_PATTERN,
    WIKI_CATEGORY_BIRTH_PATTERN,
    WIKI_CATEGORY_COUNTRY_PATTERN,
    WIKI_CATEGORY_DEATH_PATTERN,
    WIKI_CATEGORY_GAMES_PATTERN,
    WIKI_CATEGORY_MEDAL_TYPE_PATTERN,
    WIKI_COMMENT_PATTERN,
    WIKI_DATE_BC_PATTERN,
    WIKI_DATE_CIRCA_PATTERN,
    WIKI_DATE_DMY_PATTERN,
    WIKI_DATE_MDY_PATTERN,
    WIKI_DATE_MY_PATTERN,
    WIKI_DATE_TEMPLATE_PATTERN,
    WIKI_DATE_Y_PATTERN,
    WIKI_EMPTY_PARENTHESES_PATTERN,
    WIKI_EXTERNAL_LINK_PATTERN,
    WIKI_HEADING_MARKUP_PATTERN,
    WIKI_HEIGHT_CM_PATTERN,
    WIKI_HEIGHT_FT_PATTERN,
    WIKI_HEIGHT_M_PATTERN,
    WIKI_INFOBOX_PARAM_PATTERN,
    WIKI_INFOBOX_START_PATTERN,
    WIKI_INNER_TEMPLATE_PATTERN,
    WIKI_LEAD_IMAGE_PATTERN,
    WIKI_LINK_PATTERN,
    WIKI_MEDAL_TEMPLATE_PATTERN,
    WIKI_NUMBER_PATTERN,
    WIKI_OLYMPIC_TEXT_PATTERN,
    WIKI_PARENTHESIS_PATTERN,
    WIKI_REF_PATTERN,
    WIKI_SECTION_PATTERN,
    WIKI_SPACE_PATTERN,
    WIKI_STRAY_OPENING_PATTERN,
    WIKI_STRAY_SEPARATOR_PATTERN,
    WIKI_TABLE_PATTERN,
    WIKI_TAG_PATTERN,
    WIKI_WANTED_SECTION_PATTERN,
    WIKI_WEIGHT_KG_PATTERN,
    WIKI_WEIGHT_LB_PATTERN,
    WIKI_WEIGHT_ST_PATTERN,
    WIKI_YOUTH_TEXT_PATTERN,
)

FIELD_NAMES: list[str] = [
    "infobox_type",
    "name",
    "birth_name",
    "birth_date",
    "birth_year",
    "birth_circa",
    "birth_place",
    "death_date",
    "death_year",
    "death_circa",
    "death_place",
    "nationality",
    "height_cm",
    "weight_kg",
    "sport",
    "olympic_gold",
    "olympic_silver",
    "olympic_bronze",
    "category_birth_year",
    "category_death_year",
    "olympic_games",
    "category_medal_kinds",
    "category_country",
    "lead",
    "body",
]

# Infobox parameter names per attribute, first non-empty wins.
NAME_KEYS: list[str] = ["name"]
BIRTH_NAME_KEYS: list[str] = ["birth_name", "birthname", "full_name", "fullname"]
BIRTH_DATE_KEYS: list[str] = ["birth_date", "birthdate", "born", "birth_year"]
DEATH_DATE_KEYS: list[str] = ["death_date", "deathdate", "died"]
BIRTH_PLACE_KEYS: list[str] = ["birth_place", "birthplace"]
DEATH_PLACE_KEYS: list[str] = ["death_place", "deathplace"]
NATIONALITY_KEYS: list[str] = ["nationality", "country", "citizenship"]
HEIGHT_KEYS: list[str] = ["height", "height_cm", "height_m"]
WEIGHT_KEYS: list[str] = ["weight", "weight_kg"]
SPORT_KEYS: list[str] = ["sport", "sports"]


# ---------------------------------------------------------------------------------------------
# template structure
# ---------------------------------------------------------------------------------------------

def find_template_end(text: str, start: int) -> int:
    """Index after the "}}" closing the "{{" at text[start]; len(text) if unclosed (head is truncated)."""
    depth = 0
    index = start
    length = len(text)

    while index < length - 1:
        pair = text[index:index + 2]

        if pair == "{{":
            depth += 1
            index += 2
        elif pair == "}}":
            depth -= 1
            index += 2

            if depth == 0:
                return index
        else:
            index += 1

    return length


def split_top_level(body: str) -> list[str]:
    """Split on "|" that sit outside of any {{...}} and [[...]]."""
    pieces: list[str] = []
    current: list[str] = []
    template_depth = 0
    link_depth = 0
    index = 0
    length = len(body)

    while index < length:
        pair = body[index:index + 2]

        if pair == "{{":
            template_depth += 1
            current.append(pair)
            index += 2
        elif pair == "}}":
            template_depth = max(0, template_depth - 1)
            current.append(pair)
            index += 2
        elif pair == "[[":
            link_depth += 1
            current.append(pair)
            index += 2
        elif pair == "]]":
            link_depth = max(0, link_depth - 1)
            current.append(pair)
            index += 2
        elif body[index] == "|" and template_depth == 0 and link_depth == 0:
            pieces.append("".join(current))
            current = []
            index += 1
        else:
            current.append(body[index])
            index += 1

    pieces.append("".join(current))
    return pieces


def first_infobox(region: str) -> Optional[str]:
    """First "{{Infobox ...}}" including braces."""
    found = WIKI_INFOBOX_START_PATTERN.search(region)

    if found is None:
        return None

    start = found.start()
    end = find_template_end(region, start)
    return region[start:end]


def medal_table_after(region: str, infobox: str) -> str:
    """Medal block right after the infobox ({{MedalTableTop}} / {{MedalTop}} ... {{MedalBottom}}), up to a blank line."""
    start = region.find(infobox)

    if start < 0:
        return ""

    tail = region[start + len(infobox):].lstrip()

    if not tail.lower().startswith("{{medal"):
        return ""

    return tail.split("\n\n", 1)[0]


def infobox_type(infobox: str) -> str:
    found = WIKI_INFOBOX_START_PATTERN.match(WIKI_COMMENT_PATTERN.sub("", infobox))

    if found is None:
        return ""

    return found.group(1).strip().lower()


def parse_infobox(infobox: str) -> dict[str, str]:
    """{lowercase name: raw value}. Nested infoboxes (`module` param) fill what the outer one lacks."""
    without_comments = WIKI_COMMENT_PATTERN.sub("", infobox)
    inner = without_comments[2:]

    if inner.endswith("}}"):
        inner = inner[:-2]

    params: dict[str, str] = {}
    nested: list[dict[str, str]] = []

    for piece in split_top_level(inner):
        found = WIKI_INFOBOX_PARAM_PATTERN.match(piece)

        if found is None:
            continue

        key = found.group(1).strip().lower().replace(" ", "_")
        value = found.group(2).strip()

        if key not in params or params[key] == "":
            params[key] = value

        if WIKI_INFOBOX_START_PATTERN.match(value) is not None:
            nested.append(parse_infobox(value))

    for module in nested:
        for key, value in module.items():
            if key not in params or params[key] == "":
                params[key] = value

    return params


def pick(params: dict[str, str], keys: list[str]) -> str:
    for key in keys:
        value = params.get(key, "")

        if value != "":
            return value

    return ""


# ---------------------------------------------------------------------------------------------
# value clean-up
# ---------------------------------------------------------------------------------------------

def _is_number(text: str) -> bool:
    return WIKI_NUMBER_PATTERN.match(text) is not None


def _convert_text(arguments: list[str]) -> str:
    """{{convert|5|ft|10|in|cm}} -> "5 ft 10 in", {{convert|12|st|7|lb|kg}} -> "12 st 7 lb", {{convert|1.88|m|ftin}} -> "1.88 m"."""
    if len(arguments) >= 4 and _is_number(arguments[0]) and _is_number(arguments[2]):
        first_unit = arguments[1].lower()
        second_unit = arguments[3].lower()

        if first_unit in WIKI_FEET_UNITS and second_unit in WIKI_INCH_UNITS:
            return f"{arguments[0]} ft {arguments[2]} in"

        if first_unit in WIKI_STONE_UNITS and second_unit in WIKI_POUND_UNITS:
            return f"{arguments[0]} st {arguments[2]} lb"

    return " ".join(arguments[:2])


def _measure_text(name: str, named: dict[str, str]) -> str:
    """{{height|ft=5|in=10}}, {{height|m=1.88}}, {{weight|kg=70}}, {{weight|st=11|lb=4}}."""
    if name == "height":
        if "m" in named:
            return f"{named['m']} m"

        if "cm" in named:
            return f"{named['cm']} cm"

        if "ft" in named:
            return f"{named['ft']} ft {named.get('in', '0')} in"

        return ""

    if "kg" in named:
        return f"{named['kg']} kg"

    if "st" in named:
        return f"{named['st']} st {named.get('lb', '0')} lb"

    if "lb" in named:
        return f"{named['lb']} lb"

    return ""


def _template_replacement(content: str) -> str:
    parts = [part.strip() for part in content.split("|")]
    name = parts[0].lower().replace("_", " ")
    arguments = [part for part in parts[1:] if "=" not in part]
    named: dict[str, str] = {}

    for part in parts[1:]:
        if "=" in part:
            key, value = part.split("=", 1)
            named[key.strip().lower()] = value.strip()

    if name in WIKI_LIST_TEMPLATES:
        return "; ".join(argument for argument in arguments if argument != "")

    if name in WIKI_PASSTHROUGH_TEMPLATES:
        return arguments[0] if len(arguments) > 0 else ""

    if name in WIKI_CIRCA_TEMPLATES:
        return "c. " + arguments[0] if len(arguments) > 0 else "c."

    if name in WIKI_LANG_TEMPLATES:
        return arguments[-1] if len(arguments) > 1 else ""

    if name in WIKI_CONVERT_TEMPLATES:
        return _convert_text(arguments)

    if name in WIKI_MEASURE_TEMPLATES:
        return _measure_text(name, named)

    return ""


def clean_value(raw: str) -> str:
    """Wikitext value -> plain text: no comments, refs, templates, links or tags."""
    text = WIKI_COMMENT_PATTERN.sub("", raw)
    text = WIKI_REF_PATTERN.sub("", text)

    # Links first, their "|" would split template arguments.
    text = WIKI_EXTERNAL_LINK_PATTERN.sub(r"\1", text)
    text = WIKI_LINK_PATTERN.sub(r"\1", text)

    for _ in range(WIKI_MAX_TEMPLATE_DEPTH):
        replaced = WIKI_INNER_TEMPLATE_PATTERN.sub(lambda match: _template_replacement(match.group(1)), text)

        if replaced == text:
            break

        text = replaced

    text = WIKI_BULLET_PATTERN.sub("; ", text)
    text = WIKI_BREAK_PATTERN.sub("; ", text)
    text = WIKI_TAG_PATTERN.sub("", text)
    text = text.replace("'''", "").replace("''", "")
    text = html.unescape(text)
    text = WIKI_SPACE_PATTERN.sub(" ", text)
    return text.strip(" ;,")


# ---------------------------------------------------------------------------------------------
# dates
# ---------------------------------------------------------------------------------------------

class ParsedDate:
    def __init__(self, year: int, month: Optional[int], day: Optional[int], circa: bool) -> None:
        self.year: int = year
        self.month: Optional[int] = month
        self.day: Optional[int] = day
        self.circa: bool = circa

    def iso(self) -> str:
        sign = "-" if self.year < 0 else ""
        text = f"{sign}{abs(self.year):04d}"

        if self.month is not None:
            text += f"-{self.month:02d}"

            if self.day is not None:
                text += f"-{self.day:02d}"

        return text


def _valid_month(month: int) -> Optional[int]:
    if 1 <= month <= 12:
        return month

    return None


def _valid_day(day: int) -> Optional[int]:
    if 1 <= day <= 31:
        return day

    return None


def _month_from_name(name: str) -> Optional[int]:
    return WIKI_MONTHS.get(name[:3].lower())


def parse_date(raw: str) -> Optional[ParsedDate]:
    """{{birth date|1890|8|24}}, {{death date and age|...}}, {{circa|490}}, "3 December 1949 (aged 47)",
    "August 24, 1890", "August 1890", "1890", BC."""
    if raw.strip() == "":
        return None

    raw_without_comments = WIKI_COMMENT_PATTERN.sub("", raw)
    raw_without_refs = WIKI_REF_PATTERN.sub("", raw_without_comments)
    circa = False

    template = WIKI_DATE_TEMPLATE_PATTERN.search(raw_without_refs)

    if template is not None:
        numbers: list[int] = []

        for argument in template.group(1).split("|"):
            stripped = argument.strip()

            if stripped.isdigit():
                numbers.append(int(stripped))

        # Fix swapped {{birth date|22|11|1897}} (d|m|y).
        if len(numbers) >= 3 and numbers[0] <= 31 and numbers[2] >= 1000:
            numbers = [numbers[2], numbers[1], numbers[0]]

        if len(numbers) > 0 and numbers[0] > 0:
            month = _valid_month(numbers[1]) if len(numbers) > 1 else None
            day = _valid_day(numbers[2]) if len(numbers) > 2 and month is not None else None
            return ParsedDate(numbers[0], month, day, False)

    lowered = raw_without_refs.lower().replace(" ", "")

    for circa_name in WIKI_CIRCA_TEMPLATES:
        if f"{{{{{circa_name}|" in lowered:
            circa = True
            break

    text = clean_value(raw_without_refs)
    text = WIKI_PARENTHESIS_PATTERN.sub("", text)

    if WIKI_DATE_CIRCA_PATTERN.search(text) is not None:
        circa = True

    negative = WIKI_DATE_BC_PATTERN.search(text) is not None
    sign = -1 if negative else 1

    dmy = WIKI_DATE_DMY_PATTERN.search(text)

    if dmy is not None:
        month = _month_from_name(dmy.group(2))

        if month is not None:
            return ParsedDate(sign * int(dmy.group(3)), month, _valid_day(int(dmy.group(1))), circa)

    mdy = WIKI_DATE_MDY_PATTERN.search(text)

    if mdy is not None:
        month = _month_from_name(mdy.group(1))

        if month is not None:
            return ParsedDate(sign * int(mdy.group(3)), month, _valid_day(int(mdy.group(2))), circa)

    my = WIKI_DATE_MY_PATTERN.search(text)

    if my is not None:
        month = _month_from_name(my.group(1))

        if month is not None:
            return ParsedDate(sign * int(my.group(2)), month, None, circa)

    year = WIKI_DATE_Y_PATTERN.search(text)

    if year is not None:
        return ParsedDate(sign * int(year.group(1)), None, None, circa)

    return None


# ---------------------------------------------------------------------------------------------
# measurements
# ---------------------------------------------------------------------------------------------

def parse_height_cm(raw: str) -> Optional[float]:
    text = clean_value(raw)
    value: Optional[float] = None

    centimetres = WIKI_HEIGHT_CM_PATTERN.search(text)
    metres = WIKI_HEIGHT_M_PATTERN.search(text)
    feet = WIKI_HEIGHT_FT_PATTERN.search(text)

    if centimetres is not None:
        value = float(centimetres.group(1))
    elif metres is not None:
        value = float(metres.group(1)) * 100.0
    elif feet is not None:
        inches = float(feet.group(2)) if feet.group(2) is not None else 0.0
        value = float(feet.group(1)) * 30.48 + inches * 2.54

    if value is None:
        return None

    low, high = WIKI_HEIGHT_RANGE_CM

    if value < low or value > high:
        return None

    return round(value, 1)


def parse_weight_kg(raw: str) -> Optional[float]:
    text = clean_value(raw)
    value: Optional[float] = None

    kilograms = WIKI_WEIGHT_KG_PATTERN.search(text)
    stones = WIKI_WEIGHT_ST_PATTERN.search(text)
    pounds = WIKI_WEIGHT_LB_PATTERN.search(text)

    if kilograms is not None:
        value = float(kilograms.group(1))
    elif stones is not None:
        extra_pounds = float(stones.group(2)) if stones.group(2) is not None else 0.0
        value = float(stones.group(1)) * 6.35029318 + extra_pounds * 0.45359237
    elif pounds is not None:
        value = float(pounds.group(1)) * 0.45359237

    if value is None:
        return None

    low, high = WIKI_WEIGHT_RANGE_KG

    if value < low or value > high:
        return None

    return round(value, 1)


# ---------------------------------------------------------------------------------------------
# medals
# ---------------------------------------------------------------------------------------------

def _is_olympic(text: str) -> bool:
    return WIKI_OLYMPIC_TEXT_PATTERN.search(text) is not None and WIKI_YOUTH_TEXT_PATTERN.search(text) is None


def parse_medals(infobox: str) -> dict[str, int]:
    """Olympic medal counts. A {{MedalCompetition}} header scopes the medals below it;
    without a header the medal's own text decides ("1924 Summer Olympics"). Youth games don't count."""
    counts: dict[str, int] = {"gold": 0, "silver": 0, "bronze": 0}
    competition_olympic: Optional[bool] = None

    for match in WIKI_MEDAL_TEMPLATE_PATTERN.finditer(infobox):
        suffix = match.group(1).lower()
        arguments = [argument.strip() for argument in match.group(2).split("|")]

        if suffix == "":
            if len(arguments) == 0:
                continue

            kind = arguments[0].lower()
            rest = arguments[1:]
        else:
            kind = suffix
            rest = arguments

        raw_text = " ".join(rest)

        if kind == "competition":
            competition_olympic = _is_olympic(raw_text)
            continue

        if kind not in WIKI_MEDAL_KINDS:
            continue

        if competition_olympic is None:
            olympic = _is_olympic(raw_text)
        else:
            olympic = competition_olympic

        if olympic:
            counts[kind] += 1

    return counts


# ---------------------------------------------------------------------------------------------
# lead section
# ---------------------------------------------------------------------------------------------

def _find_link_end(text: str, start: int) -> int:
    """Index after the "]]" closing the "[[" at text[start]; len(text) if unclosed."""
    depth = 0
    index = start
    length = len(text)

    while index < length - 1:
        pair = text[index:index + 2]

        if pair == "[[":
            depth += 1
            index += 2
        elif pair == "]]":
            depth -= 1
            index += 2

            if depth == 0:
                return index
        else:
            index += 1

    return length


def _strip_leading_blocks(text: str) -> str:
    """Drop templates (hatnotes, medal tables, ...) and images before the first paragraph."""
    while True:
        text = text.lstrip()

        if text.startswith("{{"):
            text = text[find_template_end(text, 0):]
        elif WIKI_LEAD_IMAGE_PATTERN.match(text) is not None:
            text = text[_find_link_end(text, 0):]
        else:
            return text


def _plain_text(text: str) -> str:
    """clean_value + drops tables, flattens headings."""
    text = WIKI_TABLE_PATTERN.sub("", text)
    text = WIKI_HEADING_MARKUP_PATTERN.sub(r"\2.", text)
    plain = clean_value(text)
    plain = WIKI_EMPTY_PARENTHESES_PATTERN.sub("", plain)
    plain = WIKI_STRAY_OPENING_PATTERN.sub("(", plain)
    plain = WIKI_STRAY_SEPARATOR_PATTERN.sub(r"\1 ", plain)
    return WIKI_SPACE_PATTERN.sub(" ", plain).strip()


def _cut(plain: str, limit: int) -> str:
    if len(plain) <= limit:
        return plain

    return plain[:limit].rsplit(" ", 1)[0] + " ..."


def extract_lead_and_body(head: str) -> tuple[Optional[str], Optional[str]]:
    """(lead, body) as plain text, approximate (inline templates are dropped).

    lead: text before the first "==Heading==".
    body: wanted level-2 sections (WIKI_WANTED_SECTION_PATTERN) as "Heading\ntext", capped per section and in total."""
    text = WIKI_COMMENT_PATTERN.sub("", head)
    text = WIKI_REF_PATTERN.sub("", text)

    infobox = first_infobox(text)

    if infobox is not None:
        text = text.replace(infobox, "", 1)

    text = _strip_leading_blocks(text)
    headings = list(WIKI_SECTION_PATTERN.finditer(text))

    lead_text = text if len(headings) == 0 else text[:headings[0].start()]
    lead = _plain_text(lead_text)
    lead_result: Optional[str] = None

    if lead != "":
        lead_result = _cut(lead, WIKI_LEAD_MAX_CHARS)

    parts: list[str] = []
    used = 0

    for index, heading in enumerate(headings):
        title = heading.group(1).strip()

        if WIKI_WANTED_SECTION_PATTERN.search(clean_value(title)) is None:
            continue

        section_end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        section = _plain_text(text[heading.end():section_end])

        if section == "":
            continue

        piece = clean_value(title) + "\n" + _cut(section, WIKI_SECTION_MAX_CHARS)
        parts.append(piece)
        used += len(piece)

        if used >= WIKI_BODY_MAX_CHARS:
            break

    body_result: Optional[str] = None

    if len(parts) > 0:
        body_result = _cut("\n\n".join(parts), WIKI_BODY_MAX_CHARS)

    return lead_result, body_result


# ---------------------------------------------------------------------------------------------
# categories
# ---------------------------------------------------------------------------------------------

def from_categories(categories: list[str]) -> dict[str, object]:
    birth_year: Optional[int] = None
    death_year: Optional[int] = None
    games: set[str] = set()
    kinds: set[str] = set()
    country: Optional[str] = None

    for category in categories:
        name = WIKI_SPACE_PATTERN.sub(" ", category).strip()

        birth = WIKI_CATEGORY_BIRTH_PATTERN.match(name)

        if birth is not None and birth_year is None:
            sign = -1 if birth.group(2) is not None else 1
            birth_year = sign * int(birth.group(1))

        death = WIKI_CATEGORY_DEATH_PATTERN.match(name)

        if death is not None and death_year is None:
            sign = -1 if death.group(2) is not None else 1
            death_year = sign * int(death.group(1))

        played = WIKI_CATEGORY_GAMES_PATTERN.search(name)

        if played is not None:
            games.add(f"{played.group(1)} {played.group(2).capitalize()}")

        medal = WIKI_CATEGORY_MEDAL_TYPE_PATTERN.match(name)

        if medal is not None:
            kinds.add(medal.group(1).lower())

        if country is None:
            home = WIKI_CATEGORY_COUNTRY_PATTERN.match(name)

            if home is not None:
                country = home.group(1).strip()

    return {
        "category_birth_year": birth_year,
        "category_death_year": death_year,
        "olympic_games": sorted(games),
        "category_medal_kinds": sorted(kinds),
        "category_country": country,
    }


# ---------------------------------------------------------------------------------------------
# one person
# ---------------------------------------------------------------------------------------------

def _text_or_none(raw: str) -> Optional[str]:
    text = clean_value(raw)

    if text == "":
        return None

    return text


def extract_person(head: Optional[str], categories: Optional[list[str]]) -> dict[str, object]:
    """head: first WIKI_HEAD_CHARS of the wikitext, categories: from the whole article. Missing -> None."""
    result: dict[str, object] = {name: None for name in FIELD_NAMES}
    result["olympic_gold"] = 0
    result["olympic_silver"] = 0
    result["olympic_bronze"] = 0
    result["olympic_games"] = []
    result["category_medal_kinds"] = []
    result["birth_circa"] = False
    result["death_circa"] = False

    if head is not None and head != "":
        lead, body = extract_lead_and_body(head)
        result["lead"] = lead
        result["body"] = body
        infobox = first_infobox(head)

        if infobox is not None:
            params = parse_infobox(infobox)
            result["infobox_type"] = infobox_type(infobox)
            result["name"] = _text_or_none(pick(params, NAME_KEYS))
            result["birth_name"] = _text_or_none(pick(params, BIRTH_NAME_KEYS))
            result["birth_place"] = _text_or_none(pick(params, BIRTH_PLACE_KEYS))
            result["death_place"] = _text_or_none(pick(params, DEATH_PLACE_KEYS))
            result["nationality"] = _text_or_none(pick(params, NATIONALITY_KEYS))
            result["sport"] = _text_or_none(pick(params, SPORT_KEYS))

            born = parse_date(pick(params, BIRTH_DATE_KEYS))

            if born is not None:
                result["birth_date"] = born.iso()
                result["birth_year"] = born.year
                result["birth_circa"] = born.circa

            died = parse_date(pick(params, DEATH_DATE_KEYS))

            if died is not None:
                result["death_date"] = died.iso()
                result["death_year"] = died.year
                result["death_circa"] = died.circa

            result["height_cm"] = parse_height_cm(pick(params, HEIGHT_KEYS))
            result["weight_kg"] = parse_weight_kg(pick(params, WEIGHT_KEYS))

            medals = parse_medals(infobox + "\n" + medal_table_after(head, infobox))
            result["olympic_gold"] = medals["gold"]
            result["olympic_silver"] = medals["silver"]
            result["olympic_bronze"] = medals["bronze"]

    if categories is not None:
        result.update(from_categories(categories))

    return result