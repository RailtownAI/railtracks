"""Observability submodule: streaming Event pipeline with per-writer queues.

Feature 1 of the observability HLD. Independent of the rest of the framework:
accepts fully-formed `Event` objects; `publish_event`, contextvar reads, and
emission sites are Feature 2 follow-ups.
"""

from .models import (
    SCOPE_EVALUATION,
    SCOPE_RETRIEVAL,
    SCOPE_SESSION,
    Event,
    Timestamp,
)
from .observer import Observer, QueuePolicy
from .writers import JsonlWriter, Writer

__all__ = [
    "Event",
    "Timestamp",
    "Observer",
    "QueuePolicy",
    "Writer",
    "JsonlWriter",
    "SCOPE_SESSION",
    "SCOPE_RETRIEVAL",
    "SCOPE_EVALUATION",
]
