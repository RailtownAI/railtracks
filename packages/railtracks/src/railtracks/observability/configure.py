"""Process-wide default Observer, plus writer registration."""

from __future__ import annotations

import atexit
from typing import Callable

from ..utils.config import _disable_events
from .models import Event
from .observer import Observer
from .writers.base import Writer
from .writers.jsonl import JsonlWriter


def _default_writers() -> list[Writer]:
    """A `JsonlWriter`, unless `RAILTRACKS_DISABLE_EVENTS` is set."""
    return [] if _disable_events() else [JsonlWriter()]


observer: Observer = Observer(default_writers=_default_writers)


def configure_writers(writers: list[Writer]) -> None:
    """Replace the writers on the process-wide Observer.

    Safe to call at any time; the writers it replaces are shut down. With none configured,
    the first event starts a `JsonlWriter`, unless `RAILTRACKS_DISABLE_EVENTS` is set.
    """
    observer.configure_writers(writers)


def add_inline_listener(listener: Callable[[Event], None]) -> bool:
    """Register a synchronous listener, unless it is already registered."""
    return observer.add_listener(listener)


def inline_listeners() -> list[Callable[[Event], None]]:
    return observer.listeners


def shutdown() -> None:
    """Shut down the process-wide Observer's writers.

    This stops recording for every run in the process, not just the caller's: later events
    are ignored, and the Observer can't be restarted. It runs automatically at interpreter
    exit, so there's normally no need to call it. Safe to call more than once.
    """
    observer.shutdown()


def reset_for_tests() -> None:
    """Swap in a fresh Observer, with no writers or listeners. For test isolation only."""
    global observer
    observer = Observer(default_writers=_default_writers)


atexit.register(shutdown)
