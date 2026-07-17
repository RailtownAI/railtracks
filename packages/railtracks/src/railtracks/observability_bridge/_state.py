from __future__ import annotations

import asyncio
import logging

from railtracks.observability import Observer, Writer

logger = logging.getLogger(__name__)

_observer: Observer = Observer()
_pending_writers: list[Writer] = []
_include_default: bool = True
_started: bool = False
_start_lock: asyncio.Lock = asyncio.Lock()


def configure_writers(writers: list[Writer], *, include_default: bool = True) -> None:
    """Set the writers to register when the observer starts.

    Args:
        writers: A list of `Writer` instances to register with the observer.
        include_default: If True (the default), also register the built-in `JsonlWriter`
            at `.railtracks/data/`. If False, only the provided writers are registered.
            
    Must be called before the first `publish_event`. Replaces any previously
    configured writers. If `include_default` is True (the default), the built-in
    `JsonlWriter` at `.railtracks/data/` is also registered.
    """
    global _pending_writers, _include_default
    if _started:
        raise RuntimeError(
            "configure_writers must be called before the first publish_event"
        )
    _pending_writers = list(writers)
    _include_default = include_default


async def _ensure_started() -> Observer:
    """Start the observer and register writers on first call. Lands in Commit 3."""
    raise NotImplementedError("_ensure_started is stubbed until Commit 3")


def _reset_for_tests() -> None:
    """Clear all module-level state. For test isolation only."""
    global _pending_writers, _include_default, _started, _start_lock
    _pending_writers = []
    _include_default = True
    _started = False
    _start_lock = asyncio.Lock()
