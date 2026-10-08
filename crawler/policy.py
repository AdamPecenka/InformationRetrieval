"""Decisions about HTTP outcomes. Pure functions, easy to test."""

import constants

OUTCOME_OK = "ok"
OUTCOME_GONE = "gone"
OUTCOME_RETRY = "retry"
OUTCOME_BLOCKED = "blocked"
OUTCOME_SKIP = "skip"


def classify(status: int) -> str:
    """What the crawler should do with a response status.

    ok       200: process the page
    gone     404/410: never retry
    retry    network error, 429, 5xx: try again later
    blocked  403: the site is refusing us, the crawler stops
    skip     anything else (other 4xx, the pseudo statuses): never retry
    """
    if status == 200:
        return OUTCOME_OK
    if status in (404, 410):
        return OUTCOME_GONE
    if status == 403:
        return OUTCOME_BLOCKED
    if status == 429 or status >= 500 or status == constants.STATUS_NETWORK_ERROR:
        return OUTCOME_RETRY
    return OUTCOME_SKIP


def is_terminal_status(status: int) -> bool:
    return classify(status) in (OUTCOME_OK, OUTCOME_GONE, OUTCOME_SKIP)


def backoff_seconds(consecutive_failures: int, retry_after_seconds: float | None) -> float:
    cap = constants.BACKOFF_CAP_SECONDS

    if retry_after_seconds is not None:
        return min(max(retry_after_seconds, 0.0), cap)

    exponent = min(max(consecutive_failures - 1, 0), 20)

    return min(constants.BACKOFF_BASE_SECONDS * (2**exponent), cap)
