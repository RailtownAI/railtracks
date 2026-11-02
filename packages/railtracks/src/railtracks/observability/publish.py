"""Publish helper for the process-wide singleton Observer."""

from __future__ import annotations

from . import configure
from .models import Event


def publish_event(event: Event) -> None:
    """Publish an event through the process-wide Observer, from any thread.

    Every inline listener and writer has the event by the time this returns.
    """
    configure.observer.publish(event)
