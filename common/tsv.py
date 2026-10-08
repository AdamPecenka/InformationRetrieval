import os
from common.log import log_remove

def clean_field(value: object) -> str:
    """Collapse tabs, newlines and runs of spaces into single spaces."""
    return " ".join(str(value).split())

def format_row(fields: list[str]) -> str:
    return "\t".join(clean_field(field) for field in fields) + "\n"

def prepare_file(path: str, header: list[str]) -> None:
    """Make sure the file exists with a header and ends on a full line.

    If the previous run was killed in the middle of a write, the last line is
    incomplete. It is dropped here, otherwise the next append would glue a new
    row onto the broken one and damage both.
    """
    directory = os.path.dirname(path)
    if directory != "":
        os.makedirs(directory, exist_ok=True)

    header_line = format_row(header)

    if not os.path.exists(path) or os.path.getsize(path) == 0:
        with open(path, "w", encoding="utf-8", newline="") as file_handler:
            file_handler.write(header_line)
        return

    with open(path, "rb+") as file_handler:
        file_handler.seek(-1, os.SEEK_END)

        if file_handler.read(1) == b"\n":
            return

        file_handler.seek(0)

        data = file_handler.read()
        cut = data.rfind(b"\n") + 1

        file_handler.truncate(cut)

        log_remove(f"dropped {len(data) - cut} bytes of a truncated last row in {path}")

        if cut == 0:
            file_handler.seek(0)
            file_handler.write(header_line.encode("utf-8"))

def read_rows(path: str, header: list[str]) -> tuple[list[list[str]], int]:
    """Read all complete rows. Returns (rows, number_of_skipped_malformed_rows)."""
    rows: list[list[str]] = []
    skipped = 0

    if not os.path.exists(path):
        return rows, skipped

    expected = len(header)
    header_text = "\t".join(header)

    with open(path, "r", encoding="utf-8", newline="") as file_handler:
        is_first_line = True

        for line in file_handler:
            text = line.rstrip("\n")

            if is_first_line:
                is_first_line = False

                if text == header_text:
                    continue

            fields = text.split("\t")

            if len(fields) != expected:
                skipped += 1
                continue

            rows.append(fields)
    return rows, skipped

class TsvAppender:
    def __init__(self, path: str, header: list[str]) -> None:
        prepare_file(path, header)
        self._handle = open(path, "a", encoding="utf-8", newline="")

    def append_rows(self, rows: list[list[str]]) -> None:
        payload = "".join(format_row(row) for row in rows)
        self._handle.write(payload)
        self._handle.flush()
        os.fsync(self._handle.fileno())

    def close(self) -> None:
        self._handle.close()
