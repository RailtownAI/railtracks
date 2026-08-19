"""DuckDB connection lifecycle for the visualizer query layer.

A single :class:`~railtracks.query.EventQuery` is kept alive for the life of
the process. Callers reach it through :func:`get_query`, which reopens the
connection on first use and refreshes it whenever the set of ``*.jsonl`` files
or one of their sizes or modification times changes.
"""

from __future__ import annotations

import atexit
import threading
from pathlib import Path

from railtracks.query import EventQuery, connect

from .._logging import debug_event

_NAMESPACES = ["session", "node", "llm", "middleware"]


FileSignature = tuple[tuple[str, int, int], ...]


def _file_signature(events_dir: Path) -> FileSignature:
    """Snapshot the files that define an ``EventQuery`` view.

    DuckDB's view contains the concrete file list present at refresh time, so
    tracking only the newest mtime misses deletion of an older file and import
    of a file whose preserved timestamp predates the current newest file.
    """
    signature: list[tuple[str, int, int]] = []
    for file in sorted(events_dir.glob("*.jsonl")):
        try:
            stat = file.stat()
        except FileNotFoundError:
            # A writer or cleanup may race the directory scan. The next request
            # will see the settled file set and refresh if necessary.
            continue
        signature.append((str(file), stat.st_size, stat.st_mtime_ns))
    return tuple(signature)


class _ConnectionRegistry:
    """Holds the shared ``EventQuery`` and serialises open / refresh / close.

    The lock is a defensive posture for a future where more than one thread
    reaches this code — the current FastAPI setup runs handlers on the event
    loop thread, so at most one caller is here at a time, but the state
    transitions are cheap to guard and expensive to debug if they interleave.
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
