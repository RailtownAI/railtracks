"""Observability submodule: streaming Event pipeline with per-writer queues,
plus a process-wide default Observer.
"""

from .models import (
    SCOPE_EVALUATION,
    SCOPE_RETRIEVAL,
    SCOPE_SESSION,
    Event,
    Timestamp,
)
from .observer import Observer, QueuePolicy
from .configure import configure_writers
from .publish import publish_event
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
    "configure_writers",
    "publish_event",
]
