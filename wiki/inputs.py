import os

from common.log import log_alert, log_error

PLACEHOLDER_MARK: str = "CHANGE-ME"


def require_dir(path: str) -> bool:
    """True when path is an existing folder (a parquet dataset). Otherwise logs why not and returns False."""
    if os.path.isdir(path):
        return True

    log_error(f"input folder not found: {path}")
    return False


def require_file(path: str) -> bool:
    """True when path is an existing file. Otherwise logs why not and returns False."""
    if os.path.isfile(path):
        return True

    log_error(f"input file not found: {path}")

    if PLACEHOLDER_MARK in path:
        log_alert("the dump path is still the placeholder: set VINF_WIKI_DUMP or edit WIKI_DUMP_PATH in constants.py")

    return False