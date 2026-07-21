"""Sync publish helper for the process-wide singleton Observer."""

from __future__ import annotations

from . import configure
from .models import Event


def publish_event(event: Event) -> None:
    """Convenience wrapper to publish an Event via the process-wide singleton Observer."""
    configure.observer.publish(event)
