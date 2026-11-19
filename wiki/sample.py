"""Write a few articles' wikitext to text files, to look at real markup before writing regexes.

A long article is cut to its beginning (infobox, lead) and its end (categories, external links, where the
Olympedia link usually is). Text in the middle is replaced by a marker that says how much was cut.
"""

import os
import re

from pyspark.sql import functions as F

from common.log import log_add, log_alert, log_error, log_info
from wiki.dump import build_spark
from wiki.inputs import require_dir

MAX_TITLES: int = 50
CUT_MARKER: str = "\n\n[... {count} characters cut by wiki-sample ...]\n\n"


def shorten(text: str, head: int, tail: int) -> str:
    if len(text) <= head + tail:
        return text

    cut = len(text) - head - tail

    return text[:head] + CUT_MARKER.format(count=cut) + text[len(text) - tail:]


def file_name(page_id: int, title: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", title).strip("_")

    return f"{page_id}_{cleaned[:40]}.txt"


def run_sample(input_path: str, output_dir: str, titles: list[str], head: int, tail: int) -> int:
    if not require_dir(input_path):
        return 1

    if len(titles) > MAX_TITLES:
        log_error(f"at most {MAX_TITLES} titles at once, got {len(titles)}")
        return 1

    spark = build_spark("vinf-wiki-sample", with_xml=False)

    try:
        rows = (
            spark.read.parquet(input_path)
            .filter(F.col("title").isin(titles))
            .select("page_id", "title", "wikitext")
            .collect()
        )
    finally:
        spark.stop()

    found = {str(row["title"]) for row in rows}

    for title in titles:
        if title not in found:
            log_alert(f"not in {input_path}: {title!r} (titles must match exactly, including case)")

    os.makedirs(output_dir, exist_ok=True)

    for row in rows:
        text = str(row["wikitext"])
        shortened = shorten(text, head, tail)
        path = os.path.join(output_dir, file_name(int(row["page_id"]), str(row["title"])))

        # newline="" writes the text as it is, so the file matches the wikitext character for character.
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(shortened)

        log_add(f"{path}: {len(text)} characters, {len(shortened)} written")

    log_info(f"{len(rows)} of {len(titles)} pages written to {output_dir}")

    return 0