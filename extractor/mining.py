"""Rule-based biography mining. Hits keep the whole sentence so false positives stay visible."""

from constants.common import LIST_SEPARATOR
from regexes.extractor import (
    CAREER_EVENT_RULES,
    OCCUPATION_RULES,
    POST_CAREER_CUE_PATTERN,
    ROLE_VERB_PATTERN,
    SENTENCE_BOUNDARY_PATTERN,
    WORLD_RECORD_PATTERN,
)


def split_sentences(text: str) -> list[str]:
    parts = SENTENCE_BOUNDARY_PATTERN.split(text)
    return [part.strip() for part in parts if part.strip() != ""]


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []

    for item in items:
        if item in seen:
            continue

        seen.add(item)
        ordered.append(item)

    return ordered


def is_world_record(text: str) -> bool:
    return WORLD_RECORD_PATTERN.search(text) is not None


def mine_biography(biography: str) -> dict[str, str]:
    """career_events: "label: sentence" per rule hit. post_career: sentences about life after sport."""
    career_events: list[str] = []
    post_career: list[str] = []

    for sentence in split_sentences(biography):
        for label, pattern in CAREER_EVENT_RULES:
            if pattern.search(sentence) is not None:
                career_events.append(f"{label}: {sentence}")

        has_cue = POST_CAREER_CUE_PATTERN.search(sentence) is not None
        has_role_verb = ROLE_VERB_PATTERN.search(sentence) is not None
        has_occupation = any(pattern.search(sentence) is not None for _, pattern in OCCUPATION_RULES)

        if has_cue or (has_role_verb and has_occupation):
            post_career.append(sentence)

    return {
        "career_events": LIST_SEPARATOR.join(_unique(career_events)),
        "post_career": LIST_SEPARATOR.join(_unique(post_career)),
    }