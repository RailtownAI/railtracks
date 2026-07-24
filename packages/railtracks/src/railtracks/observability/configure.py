"""Process-wide default Observer, plus writer registration."""

from __future__ import annotations

from .observer import Observer
from .writers.base import Writer

observer: Observer = Observer()


def configure_writers(writers: list[Writer]) -> None:
    """Set the writers to register on the singleton Observer on first start().

    Delegates to `observer.configure_writers`. Must be called before the
    observer has started; raises `RuntimeError` otherwise.
    """
    observer.configure_writers(writers)


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
