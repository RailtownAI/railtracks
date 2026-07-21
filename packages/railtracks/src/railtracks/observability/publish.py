"""Sync fire-and-forget publish helper for the Observer."""

from __future__ import annotations

import asyncio
import logging

from .configure import ensure_started
from .models import Event

logger = logging.getLogger(__name__)

_pending_tasks: set[asyncio.Task] = set()


def publish_event(event: Event) -> None:
    """Publish an Event via the process-wide Observer.

    Sync fire-and-forget. If no event loop is running, logs a WARNING and drops
    the event. Sync by design to leave room for sync callers that might slip in later. Any
    other failure (writer errors, observer not ready) logs at WARNING inside
    the fire-and-forget task and doesn't propagate to the caller.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning(
            "publish_event called with no running loop; dropping event %s",
            event.event_id,
        )
        return
    task = loop.create_task(_publish(event))
    _pending_tasks.add(task)
    task.add_done_callback(_pending_tasks.discard)


async def _publish(event: Event) -> None:
    try:
        observer = await ensure_started()
        observer.publish(event)
    except Exception:
        logger.warning("publish_event failed", exc_info=True)


def reset_for_tests() -> None:
    """Clear the pending-tasks set. For test isolation only."""
    _pending_tasks.clear()
