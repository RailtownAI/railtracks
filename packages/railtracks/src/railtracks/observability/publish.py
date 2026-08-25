"""Sync publish helper for the process-wide singleton Observer."""

from __future__ import annotations

from ..utils.logging.create import get_rt_logger
from . import configure
from .models import Event

logger = get_rt_logger(__name__)


async def publish_event(event: Event) -> None:
    """Convenience wrapper to publish an Event via the process-wide singleton Observer.

    Inline listeners run first and are isolated from each other: one raising must
    neither lose the event for the others nor stop it reaching the Observer.
    """
    for listener in configure.inline_listeners():
        try:
            listener(event)
        except Exception:
            logger.exception(
                "observability: inline listener failed on %s", event.event_type
            )

    await configure.observer.publish(event)
