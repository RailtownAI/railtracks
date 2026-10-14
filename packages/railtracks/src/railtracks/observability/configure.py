"""Process-wide default Observer, plus writer registration."""

from __future__ import annotations

import threading
from typing import Callable

from ..utils.config import _disable_events
from ..utils.logging.create import get_rt_logger
from .models import Event
from .observer import Observer
from .writers.base import Writer
from .writers.jsonl import JsonlWriter

logger = get_rt_logger(__name__)

observer: Observer = Observer()

# Two runs starting together on different threads must not both inject the default writer
_default_writer_lock = threading.Lock()

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
    """Take a reference on the singleton observer, starting it if needed, and return it.

    Pair every call with `shutdown()`. Auto-registers a default `JsonlWriter` when no
    writers have been configured and `RAILTRACKS_DISABLE_EVENTS` is unset.
    """
    with _default_writer_lock:
        if (
            not observer._running
            and not observer._pending_writers
            and not _disable_events()
        ):
            observer.configure_writers([JsonlWriter()])
    await observer.start()
    return observer


async def shutdown() -> None:
    """Release the reference taken by `ensure_started()`.

    The last release drains per-writer queues and stops the consumer tasks. Safe to
    call when the observer isn't running.
    """
    await observer.shutdown()


def reset_for_tests() -> None:
    """Clear singleton state. For test isolation only.

    Stops the current Observer's thread without draining and swaps in a fresh
    `Observer`, so writers from a previous test don't leak into the next one.
    """
    global observer
    observer._stop_thread()
    observer = Observer()
    _inline_listeners.clear()
