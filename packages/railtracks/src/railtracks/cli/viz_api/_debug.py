"""Debug-mode toggle for the viz_api.

The CLI calls :func:`set_debug` before starting the server; every noisy print
inside the API surface (per-request preamble, per-query timing) fires only
when the flag is on. Server startup and endpoint listing stay unconditional.
"""

from __future__ import annotations

from ..io import print_status

_DEBUG = False


def set_debug(value: bool) -> None:
    global _DEBUG
    _DEBUG = value


def is_debug() -> bool:
    return _DEBUG


def debug_print(message: str) -> None:
    if _DEBUG:
        print_status(message)
