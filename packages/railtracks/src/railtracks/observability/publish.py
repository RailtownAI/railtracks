"""Sync publish helper for the process-wide singleton Observer."""

from __future__ import annotations

import logging

from . import configure
from .models import Event

logger = logging.getLogger(__name__)


def publish_event(event: Event) -> None:
    """Publish an Event via the process-wide singleton Observer.

    Sync — fan-out is deterministic and in call order. The observer must have
    been started; call `observability.ensure_started()` (or wait for
    Session.__enter__ wiring, in a follow-up ticket) before publishing.

    If not started, logs a WARNING and drops the event rather than raising.
    """
    try:
        configure._observer.publish(event)
    except RuntimeError as e:
        logger.warning(
            "publish_event: observer not started; dropping event %s. "
            "Call `await observability.ensure_started()` before publishing.",
            event.event_id,
        )
        raise e
