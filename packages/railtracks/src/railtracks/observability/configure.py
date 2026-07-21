"""Process-wide default Observer, plus writer registration.

Thin wrapper over `Observer`: Holds the shared singleton instance and routes
module-level `configure_writers` and `ensure_started` to it. All the real
lifecycle logic (pending writers, double-checked start, running flag) lives
on the `Observer` class now.

Callers who want their own Observer can still construct one directly from
`observability.Observer`; this module just wires up a shared default for the
common case.
"""

from __future__ import annotations

import logging

from .observer import Observer
from .writers.base import Writer

logger = logging.getLogger(__name__)

observer: Observer = Observer()


def configure_writers(writers: list[Writer]) -> None:
    """Set the writers to register on the singleton Observer on first start().

    Delegates to `observer.configure_writers`. Must be called before the
    observer has started; raises `RuntimeError` otherwise.
    """
    observer.configure_writers(writers)


async def ensure_started() -> Observer:
    """Start the singleton observer if not already started, return it.
    """
    await observer.start()
    return observer


async def shutdown() -> None:
    """Drain per-writer queues and stop the singleton Observer's consumer tasks.

    safe to call when the observer isn't running.
    """
    await observer.shutdown()


def reset_for_tests() -> None:
    """Clear singleton state. For test isolation only.

    Swaps in a fresh `Observer` so consumer tasks from a previous test's event
    loop don't leak into the next one.
    """
    global observer
    observer = Observer()
