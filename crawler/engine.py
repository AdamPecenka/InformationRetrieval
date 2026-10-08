import time
from dataclasses import dataclass
from urllib.parse import urlsplit

import constants
from common.clock import utc_now_iso
from common.log import log_add, log_alert, log_error, log_info, log_remove
from crawler.fetcher import FetchResult, Fetcher
from crawler.frontier import Frontier, FrontierEntry
from crawler.links import athlete_flags, athlete_id, extract_links
from crawler.policy import (
    OUTCOME_BLOCKED,
    OUTCOME_OK,
    OUTCOME_RETRY,
    backoff_seconds,
    classify,
)
from crawler.storage import FetchedLog, FetchRecord, write_page

CONTINUE = "continue"
STOP = "stop"

@dataclass
class CrawlContext:
    fetcher: Fetcher
    frontier: Frontier
    fetched_log: FetchedLog
    attempts: dict[str, int]
    consecutive_failures: int
    run_fetches: int
    stored_count: int
    stored_bytes: int
    started_at: float


def run_crawler(max_pages: int | None = None) -> int:
    fetcher = Fetcher()

    wait_for_robots(fetcher)

    fetched_log = FetchedLog()
    state = fetched_log.load_state()

    frontier = Frontier()
    frontier.load(state.done)

    if frontier.known_count() == 0:
        frontier.seed(constants.SEED_URLS)
        log_add(f"seeded the frontier with {len(constants.SEED_URLS)} URL(s)")

    log_info(
        f"resuming with {frontier.known_count()} known URLs, "
        f"{len(state.done)} finished, {len(frontier)} pending, "
        f"{state.stored_count} pages stored so far"
    )

    context = CrawlContext(
        fetcher=fetcher,
        frontier=frontier,
        fetched_log=fetched_log,
        attempts={},
        consecutive_failures=0,
        run_fetches=0,
        stored_count=state.stored_count,
        stored_bytes=state.stored_bytes,
        started_at=time.monotonic(),
    )

    exit_code = 0

    try:
        exit_code = crawl_loop(context, max_pages)
    except KeyboardInterrupt:
        log_info("interrupted; everything committed so far is consistent, run again to resume")
        exit_code = 130
    finally:
        log_info(
            f"stopping after {context.run_fetches} fetches this run, "
            f"{context.stored_count} pages stored in total, {len(context.frontier)} still pending"
        )
    return exit_code


def wait_for_robots(fetcher: Fetcher) -> None:
    """Do not crawl until robots.txt could be read, however long that takes."""
    failures = 0

    while not fetcher.load_robots():
        failures += 1
        pause = backoff_seconds(failures, None)
        log_error(f"cannot read robots.txt yet, retrying in {pause:.0f}s")
        time.sleep(pause)


def crawl_loop(context: CrawlContext, max_pages: int | None) -> int:
    while True:
        if max_pages is not None and context.run_fetches >= max_pages:
            log_info(f"reached --max-pages {max_pages}")
            return 0

        entry = context.frontier.pop()

        if entry is None:
            log_info("the frontier is empty, crawl complete")
            return 0

        if context.fetcher.robots_refresh_due():
            if not context.fetcher.load_robots():
                log_alert("could not refresh robots.txt, keeping the previous rules")

        action = handle_entry(context, entry)
        context.run_fetches += 1

        if action == STOP:
            return 1

        report_progress(context)


def handle_entry(context: CrawlContext, entry: FrontierEntry) -> str:
    url = entry.url

    if not context.fetcher.is_allowed(url):
        append_record(context, url, constants.STATUS_ROBOTS_DISALLOWED, 0, 0)
        log_remove(f"robots.txt disallows {url}")

        return CONTINUE

    attempt = context.attempts.get(url, 0) + 1
    context.attempts[url] = attempt
    result = context.fetcher.fetch(url)
    outcome = classify(result.status)

    if outcome == OUTCOME_RETRY:
        return handle_retry(context, entry, result, attempt)

    context.consecutive_failures = 0
    context.attempts.pop(url, None)

    if outcome == OUTCOME_OK:
        return handle_ok(context, entry, result, attempt)
    if outcome == OUTCOME_BLOCKED:
        append_record(context, url, result.status, attempt, len(result.body))
        log_alert(f"{url} answered 403, the site is refusing us. Stopping. Run again later.")
        return STOP

    append_record(context, url, result.status, attempt, len(result.body))
    log_remove(f"{url} -> HTTP {result.status}, not retrying")

    return CONTINUE


def handle_ok(context: CrawlContext, entry: FrontierEntry, result: FetchResult, attempt: int) -> str:
    url = entry.url

    if is_offsite(result.final_url):
        append_record(context, url, constants.STATUS_OFFSITE_REDIRECT, attempt, 0)
        log_remove(f"{url} redirected off-site to {result.final_url}")
        return CONTINUE

    if "text/html" not in result.content_type.lower():
        append_record(context, url, result.status, attempt, len(result.body))
        log_remove(f"{url} is not HTML ({result.content_type})")
        return CONTINUE

    page_html = result.body.decode("utf-8", errors="replace")
    has_bio = False
    has_medal = False
    stored = False
    file_path = ""
    identifier = athlete_id(url)

    if identifier is not None:
        has_bio, has_medal = athlete_flags(page_html)
        if has_bio and has_medal:
            file_path = write_page(identifier, result.body)
            stored = True

    links = extract_links(page_html, result.final_url)

    now = utc_now_iso()

    discovered = [FrontierEntry(link_url, entry.depth + 1, url, anchor, now) for link_url, anchor in links]

    added = context.frontier.add_many(discovered)

    record = FetchRecord(
        url=url,
        status=result.status,
        attempt=attempt,
        fetched_at=now,
        size=len(result.body),
        has_bio=has_bio,
        has_medal=has_medal,
        stored=stored,
        file=file_path,
    )

    context.fetched_log.append(record)

    log_info(
        f"GET {url} -> 200, {len(result.body)} B, depth {entry.depth}, "
        f"{len(links)} links, {added} new, queue {len(context.frontier)}"
    )

    if stored:
        context.stored_count += 1
        context.stored_bytes += len(result.body)
        log_add(f"stored {file_path}")

    elif identifier is not None:
        log_remove(f"discarded athlete {identifier} (biography={has_bio}, medal={has_medal})")

    return CONTINUE

def handle_retry(context: CrawlContext, entry: FrontierEntry, result: FetchResult, attempt: int) -> str:
    url = entry.url
    context.consecutive_failures += 1
    reason = result.error

    if reason == "":
        reason = f"HTTP {result.status}"

    append_record(context, url, result.status, attempt, len(result.body))

    if attempt >= constants.MAX_ATTEMPTS:
        # Before abandoning the URL, check that the site itself is reachable.
        # If it is not, this is an outage and the URL is not at fault.
        if context.fetcher.load_robots():
            append_record(context, url, constants.STATUS_GAVE_UP, attempt, 0)
            log_error(f"giving up on {url} after {attempt} attempts ({reason})")

            context.attempts.pop(url, None)
            context.consecutive_failures = 0

            return CONTINUE

        log_alert("the site looks unreachable (robots.txt probe failed), will keep retrying")

    pause = backoff_seconds(context.consecutive_failures, result.retry_after_seconds)
    log_error(f"{url}: {reason}; attempt {attempt}, backing off {pause:.0f}s")
    context.frontier.push_front(entry)

    time.sleep(pause)

    return CONTINUE


def append_record(context: CrawlContext, url: str, status: int, attempt: int, size: int) -> None:
    record = FetchRecord(
        url=url,
        status=status,
        attempt=attempt,
        fetched_at=utc_now_iso(),
        size=size,
        has_bio=False,
        has_medal=False,
        stored=False,
        file="",
    )
    context.fetched_log.append(record)


def is_offsite(final_url: str) -> bool:
    final_host = urlsplit(final_url).netloc.lower()
    base_host = urlsplit(constants.BASE_URL).netloc.lower()
    return final_host != base_host


def report_progress(context: CrawlContext) -> None:
    if context.run_fetches % constants.PROGRESS_EVERY_FETCHES != 0:
        return

    elapsed = time.monotonic() - context.started_at
    rate = 0.0

    if elapsed > 0:
        rate = context.run_fetches / elapsed

    megabytes = context.stored_bytes / (1024 * 1024)

    log_info(
        f"progress: {context.run_fetches} fetches this run ({rate:.2f}/s), "
        f"{context.stored_count} pages stored ({megabytes:.1f} MB unshrunk), "
        f"{len(context.frontier)} pending"
    )
