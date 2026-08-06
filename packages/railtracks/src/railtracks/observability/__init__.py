"""Observability submodule: streaming Event pipeline with per-writer queues,
plus a process-wide default Observer.
"""

from .configure import (
    add_inline_listener,
    configure_writers,
    ensure_started,
    shutdown,
)
from .models import (
    SCOPE_EVALUATION,
    SCOPE_RETRIEVAL,
    SCOPE_SESSION,
    Event,
    Timestamp,
)
from .node_internals import NodeInternalsCollector
from .observer import Observer, QueuePolicy
from .publish import publish_event
from .writers import JsonlWriter, Writer

__all__ = [
    "Event",
    "Timestamp",
    "Observer",
    "QueuePolicy",
    "Writer",
    "JsonlWriter",
    "NodeInternalsCollector",
    "SCOPE_SESSION",
    "SCOPE_RETRIEVAL",
    "SCOPE_EVALUATION",
    "configure_writers",
    "add_inline_listener",
    "publish_event",
    "ensure_started",
    "shutdown",
]
