"""Sync publish helper for the process-wide singleton Observer."""

from __future__ import annotations

import asyncio

from ..utils.logging.create import get_rt_logger
from . import configure
from .models import Event
from .observer import Observer

logger = get_rt_logger(__name__)


async def publish_event(event: Event) -> None:
    """Convenience wrapper to publish an Event via the process-wide singleton Observer.

    Inline listeners run first and are isolated from each other: one raising must
    neither lose the event for the others nor stop it reaching the Observer.
    """
    _run_inline_listeners(event)

    await configure.observer.publish(event)


def publish_event_nowait(event: Event) -> None:
    """Sync counterpart of `publish_event`, callable from any thread.

    `asyncio.Queue` is not thread-safe, so a caller off the observer's loop is handed back
    to it with `call_soon_threadsafe`.

    Raises:
        RuntimeError: If the observer is not running.
    """
    observer = configure.observer
    loop = observer.loop
    if loop is None:
        raise RuntimeError("Observer is not running.")

    try:
        on_loop = asyncio.get_running_loop() is loop
    except RuntimeError:
        on_loop = False

    if on_loop:
        _run_inline_listeners(event)
        observer.publish_nowait(event)
    else:
        # Bound now rather than read in the callback: reset_for_tests() swaps the singleton.
        loop.call_soon_threadsafe(_deliver_from_thread, observer, event)


def _run_inline_listeners(event: Event) -> None:
    for listener in configure.inline_listeners():
        try:
            listener(event)
        except Exception:
            logger.exception(
                "observability: inline listener failed on %s", event.event_type
            )


def _deliver_from_thread(observer: Observer, event: Event) -> None:
    """Deliver an event scheduled onto the loop by another thread.

    Runs as a loop callback, so it must not raise, and the observer may have shut down
    since the event was scheduled.
    """
    try:
        _run_inline_listeners(event)
        observer.publish_nowait(event)
    except Exception:
        logger.debug(
            "observability: dropped %s recorded off-loop",
            event.event_type,
            exc_info=True,
        )
