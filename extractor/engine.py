import os
from collections import Counter

from common.log import log_alert, log_error, log_info
from constants.common import LIST_SEPARATOR, RAW_ATHLETES_DIR
from constants.extractor import (
    ATHLETE_COLUMNS,
    EXTRACT_MAX_PAGE_WARNINGS,
    EXTRACT_PROGRESS_EVERY_PAGES,
    MEDAL_NAMES,
    SECTION_BIOGRAPHICAL,
    SECTION_BIOGRAPHY,
    SECTION_LIST_MENTIONS,
    SECTION_OTHER_PARTICIPATIONS,
    SECTION_RESULTS,
)
from extractor.biodata import parse_biodata, parse_medal_counts, parse_personal_bests
from extractor.markup import list_items_of, paragraphs_of, prepare_body, split_sections, text_of
from extractor.mining import is_world_record, mine_biography
from extractor.results import parse_other_participations, parse_results
from extractor.storage import ExtractedStore, list_pages, read_page


def extract_page(page_html: str, athlete_id: str) -> tuple[dict[str, str], list[dict[str, str]], list[str]]:
    """Parse one stored athlete page. Returns (athlete row, result rows, warnings)."""
    body = prepare_body(page_html)
    sections = split_sections(body)
    warnings: list[str] = []

    biographical = sections.get(SECTION_BIOGRAPHICAL)
    if biographical is None:
        warnings.append(f"missing section '{SECTION_BIOGRAPHICAL}'")
        biographical = body

    biography_html = sections.get(SECTION_BIOGRAPHY)
    if biography_html is None:
        warnings.append(f"missing section '{SECTION_BIOGRAPHY}'")
        biography_html = ""

    results_html = sections.get(SECTION_RESULTS, "")
    mentions_html = sections.get(SECTION_LIST_MENTIONS, "")
    participations_html = sections.get(SECTION_OTHER_PARTICIPATIONS, "")

    athlete: dict[str, str] = {column: "" for column in ATHLETE_COLUMNS}
    athlete["athlete_id"] = athlete_id
    athlete.update(parse_biodata(biographical))

    if athlete["full_name"] == "":
        warnings.append("no 'Full name' row")

    results = parse_results(results_html, athlete_id)

    if results_html != "" and not results:
        warnings.append("results table not parsed")

    medals = parse_medal_counts(biographical)
    counted = Counter(result["medal"] for result in results)

    if medals:
        athlete["medals_gold"] = medals.get("gold", "0")
        athlete["medals_silver"] = medals.get("silver", "0")
        athlete["medals_bronze"] = medals.get("bronze", "0")
        athlete["medals_total"] = medals.get("total", "")
    else:
        # No medal box = no athlete medals (coach medals are in another table).
        athlete["medals_gold"] = str(counted["Gold"])
        athlete["medals_silver"] = str(counted["Silver"])
        athlete["medals_bronze"] = str(counted["Bronze"])
        athlete["medals_total"] = str(sum(counted[name] for name in MEDAL_NAMES))

        if athlete["medals_total"] != "0":
            warnings.append("no medal box but results show medals")

    athlete["other_participations"] = LIST_SEPARATOR.join(parse_other_participations(participations_html))
    athlete["personal_bests"] = parse_personal_bests(biographical, biography_html)

    mentions = list_items_of(mentions_html)
    athlete["list_mentions"] = LIST_SEPARATOR.join(mentions)
    athlete["world_records"] = LIST_SEPARATOR.join(item for item in mentions if is_world_record(item))

    paragraphs = paragraphs_of(biography_html)
    biography = " ".join(paragraphs)

    if biography == "":
        biography = text_of(biography_html)

    athlete["biography"] = biography
    athlete.update(mine_biography(biography))

    return athlete, results, warnings


def _athlete_id(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


def run_extractor(rebuild: bool = False) -> int:
    pages = list_pages()

    if not pages:
        log_error(f"no athlete pages in {RAW_ATHLETES_DIR}, run the crawler first")
        return 1

    store = ExtractedStore(rebuild)
    todo = [path for path in pages if _athlete_id(path) not in store.done]

    log_info(f"{len(pages)} pages, {len(pages) - len(todo)} already extracted, {len(todo)} to do")

    if not todo:
        store.close()
        log_info("nothing to do (use --rebuild after changing the extraction rules)")
        return 0

    processed = 0
    failed = 0
    result_rows = 0
    warned_pages = 0
    warning_counts: Counter[str] = Counter()

    try:
        for path in todo:
            athlete_id = _athlete_id(path)

            try:
                athlete, results, warnings = extract_page(read_page(path), athlete_id)
            except Exception as error:  # don't let one page kill the run
                failed += 1
                log_error(f"{athlete_id}: {type(error).__name__}: {error}")
                continue

            store.write(athlete, results)
            processed += 1
            result_rows += len(results)

            if warnings:
                warned_pages += 1
                warning_counts.update(warnings)

                if warned_pages <= EXTRACT_MAX_PAGE_WARNINGS:
                    log_alert(f"{athlete_id}: {'; '.join(warnings)}")

            if processed % EXTRACT_PROGRESS_EVERY_PAGES == 0:
                log_info(f"{processed}/{len(todo)} pages, {result_rows} result rows")
    except KeyboardInterrupt:
        log_alert(f"interrupted after {processed} pages, rerun to continue")
        return 130
    finally:
        store.close()

    log_info(f"done: {processed} athletes, {result_rows} result rows, {failed} failed")

    for message, count in warning_counts.most_common():
        log_alert(f"{count} pages: {message}")

    if failed > 0:
        return 1

    return 0