"""Process-wide default Observer, plus writer registration."""

from __future__ import annotations

from typing import Callable

from .models import Event
from .observer import Observer
from .writers.base import Writer

observer: Observer = Observer()

# Called synchronously before the event reaches the Observer's per-writer queues
_inline_listeners: list[Callable[[Event], None]] = []


def configure_writers(writers: list[Writer]) -> None:
    """Set the writers to register on the singleton Observer on first start().

    Delegates to `observer.configure_writers`. Must be called before the
    observer has started; raises `RuntimeError` otherwise.
    """
    observer.configure_writers(writers)


def add_inline_listener(listener: Callable[[Event], None]) -> bool:
    """Register a synchronous listener, unless it is already registered."""
    if listener in _inline_listeners:
        return False
    _inline_listeners.append(listener)
    return True


def inline_listeners() -> list[Callable[[Event], None]]:
    return list(_inline_listeners)


async def ensure_started() -> Observer:
    """Start the singleton observer if not already started, return it."""
    await observer.start()
    return observer


async def shutdown() -> None:
    """Drain per-writer queues and stop the singleton Observer's consumer tasks.

    Safe to call when the observer isn't running.
    """
    await observer.shutdown()


def reset_for_tests() -> None:
    """Clear singleton state. For test isolation only.

    Swaps in a fresh `Observer` so consumer tasks from a previous test's event
    loop don't leak into the next one.
    """
    global observer
    observer = Observer()
    _inline_listeners.clear()
