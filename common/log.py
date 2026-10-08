"""Tagged console output.

[i] general log      [+] addition      [-] removal / discard
[E] error            [!] serious       [_] user input
"""

import sys
import time


def _emit(tag: str, message: str, to_stderr: bool = False) -> None:
    stream = sys.stderr if to_stderr else sys.stdout
    stamp = time.strftime("%H:%M:%S")
    print(f"[{tag}] {stamp} {message}", file=stream, flush=True)


def log_info(message: str) -> None:
    _emit("i", message)


def log_add(message: str) -> None:
    _emit("+", message)


def log_remove(message: str) -> None:
    _emit("-", message)


def log_error(message: str) -> None:
    _emit("E", message, to_stderr=True)


def log_alert(message: str) -> None:
    _emit("!", message, to_stderr=True)


def log_input(message: str) -> None:
    _emit("_", message)
