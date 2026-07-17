"""Process-wide default Observer, plus writer registration.

This is the runtime state that backs the module-level `publish_event` and
`configure_writers` helpers. Callers who want their own Observer can still
construct one directly from `observability.Observer`; this module just wires
up a shared default for the common case.

"""

from __future__ import annotations

import asyncio
import logging

from .observer import Observer
from .writers.base import Writer

logger = logging.getLogger(__name__)

_observer: Observer = Observer()
_pending_writers: list[Writer] = []
_started: bool = False
_start_lock: asyncio.Lock = asyncio.Lock()


def configure_writers(writers: list[Writer]) -> None:
    """Set the writers to register on the singleton Observer when it starts.

    Must be called before the first `publish_event`. Replaces any previously
    configured writers.
    """
    global _pending_writers
    if _started:
        raise RuntimeError(
            "configure_writers must be called before the observer has started"
        )
    _pending_writers = list(writers)


async def _ensure_started() -> Observer:
    """Start the singleton observer and register writers on the first call.

    This is idempotent and thread-safe, so multiple concurrent calls will only start the
    observer once. Returns the singleton Observer.
    """
    global _started
    if _started:
        return _observer
    async with _start_lock:
        if _started:
            return _observer
        await _observer.start()
        for i, writer in enumerate(_pending_writers):
            await _observer.register(writer, f"writer-{i}")
        _started = True
    return _observer


def _reset_for_tests() -> None:
    """Clear singleton state. For test isolation only.

    Swaps in a fresh `Observer` so consumer tasks from a previous test's event
    loop don't leak into the next one.
    """
    global _observer, _pending_writers, _started, _start_lock
    _observer = Observer()
    _pending_writers = []
    _started = False
    _start_lock = asyncio.Lock()
