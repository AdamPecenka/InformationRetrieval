import bz2
import os
from typing import TextIO

from common.log import log_add, log_error, log_info
from wiki.inputs import require_file

PAGE_END_LINE: str = "</page>"
ROOT_END_LINE: str = "</mediawiki>"


def open_text(path: str) -> TextIO:
    """Open the dump as text. Only the start is read, so a .bz2 is never fully decompressed."""
    if path.lower().endswith(".bz2"):
        return bz2.open(path, mode="rt", encoding="utf-8", newline="")

    return open(path, mode="r", encoding="utf-8", newline="")


def write_slice(source_path: str, target_path: str, page_count: int) -> int:
    """Copy the dump header and the first page_count pages into a plain XML file.

    The dump puts every structural tag on its own line, which the line matching
    below relies on. Returns the number of pages written.
    """
    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)

    temp_path = target_path + ".tmp"
    pages = 0
    closed = False

    with open_text(source_path) as source:
        with open(temp_path, "w", encoding="utf-8", newline="") as target:
            for line in source:
                target.write(line)
                stripped = line.strip()

                if stripped == ROOT_END_LINE:
                    closed = True
                    break

                if stripped == PAGE_END_LINE:
                    pages += 1

                    if pages >= page_count:
                        break

            if not closed:
                target.write(ROOT_END_LINE + "\n")

    os.replace(temp_path, target_path)

    return pages


def run_slice(input_path: str, output_path: str, page_count: int) -> int:
    if page_count < 1:
        log_error("--pages must be at least 1")
        return 1

    if not require_file(input_path):
        return 1

    log_info(f"copying the first {page_count} pages of {input_path}")

    written = write_slice(input_path, output_path, page_count)

    if written == 0:
        log_error("no <page> found, is this really a Wikipedia dump?")
        return 1

    megabytes = os.path.getsize(output_path) / (1024 * 1024)
    log_add(f"wrote {written} pages ({megabytes:.1f} MB) to {output_path}")

    return 0