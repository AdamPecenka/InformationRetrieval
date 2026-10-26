"""Rule based mining of the free-text biography.

A rule only decides whether a sentence is a candidate. The whole sentence is
kept, so a wrong guess stays visible and can be counted in the evaluation.
"""

import constants


def split_sentences(text: str) -> list[str]:
    parts = constants.SENTENCE_BOUNDARY_PATTERN.split(text)
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
    return constants.WORLD_RECORD_PATTERN.search(text) is not None


def mine_biography(biography: str) -> dict[str, str]:
    """career_events: retirement / comeback / injury sentences. post_career: sentences about life after sport."""
    career_events: list[str] = []
    post_career: list[str] = []

    for sentence in split_sentences(biography):
        for label, pattern in constants.CAREER_EVENT_RULES:
            if pattern.search(sentence) is not None:
                career_events.append(f"{label}: {sentence}")

        has_cue = constants.POST_CAREER_CUE_PATTERN.search(sentence) is not None
        has_role_verb = constants.ROLE_VERB_PATTERN.search(sentence) is not None
        has_occupation = any(pattern.search(sentence) is not None for _, pattern in constants.OCCUPATION_RULES)

        if has_cue or (has_role_verb and has_occupation):
            post_career.append(sentence)

    return {
        "career_events": constants.LIST_SEPARATOR.join(_unique(career_events)),
        "post_career": constants.LIST_SEPARATOR.join(_unique(post_career)),
    }