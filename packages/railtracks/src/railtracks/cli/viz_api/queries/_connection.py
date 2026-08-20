"""DuckDB connection lifecycle for the visualizer query layer.

A single :class:`~railtracks.query.EventQuery` is kept alive for the life of
the process. Callers reach it through :func:`get_query`, which reopens the
connection on first use and refreshes it whenever the set of ``*.jsonl`` file
paths changes. DuckDB re-reads the contents behind existing paths on each query,
so appends and same-path replacements need no view rebuild.
"""

from __future__ import annotations

import atexit
import threading
from pathlib import Path

from railtracks.query import EventQuery, connect

from .._logging import debug_event

_NAMESPACES = ["session", "node", "llm", "middleware"]


FileSignature = tuple[str, ...]


def _file_signature(events_dir: Path) -> FileSignature:
    """Return the concrete file paths captured by the DuckDB view.

    The view re-reads existing paths when it executes, including after an append
    or same-path replacement. Only additions and deletions change the view
    definition and require ``refresh()``.
    """
    return tuple(str(file) for file in sorted(events_dir.glob("*.jsonl")))


class _ConnectionRegistry:
    """Holds the shared ``EventQuery`` and serialises open / refresh / close.

    FastAPI reaches the registry through async dependencies, keeping acquisition
    and the route's synchronous DuckDB work on the event-loop thread. The lock
    still protects shutdown and direct callers from interleaving state changes.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._query: EventQuery | None = None
        self._events_dir: Path | None = None
        self._signature: FileSignature = ()

    def get(self, events_dir: Path) -> EventQuery | None:
        with self._lock:
            signature = _file_signature(events_dir)
            if not signature:
                self._close_unlocked()
                return None

            if self._query is None or events_dir != self._events_dir:
                self._close_unlocked()
                self._query = connect(events_dir, _NAMESPACES)
                self._events_dir = events_dir
                self._signature = signature
                debug_event(
                    "event_store_opened",
                    events_dir=str(events_dir),
                    file_count=len(signature),
                )
                return self._query
            if signature != self._signature:
                self._query.refresh()
                self._signature = signature
                debug_event(
                    "event_store_refreshed",
                    events_dir=str(events_dir),
                    file_count=len(signature),
                )
            return self._query

    def close(self) -> None:
        with self._lock:
            self._close_unlocked()

    def _close_unlocked(self) -> None:
        if self._query is not None:
            self._query.close()
            self._query = None
            debug_event("event_store_closed")
        self._events_dir = None
        self._signature = ()


_registry = _ConnectionRegistry()


def get_query(events_dir: Path) -> EventQuery | None:
    """Return the shared query, or ``None`` when no event files exist."""
    return _registry.get(events_dir)


def close_query() -> None:
    """Close the shared connection. Called from shutdown handlers and tests."""
    _registry.close()


atexit.register(close_query)
