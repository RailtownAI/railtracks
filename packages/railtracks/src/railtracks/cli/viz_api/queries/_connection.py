"""DuckDB connection lifecycle for the visualizer query layer.

A single :class:`~railtracks.query.EventQuery` is kept alive for the life of
the process. Callers reach it through :func:`get_query`, which reopens the
connection on first use and after that only re-scans the ``*.jsonl`` files
when their newest mtime has moved. The scan lands once per write, not once
per read.
"""

from __future__ import annotations

import atexit
import threading
from pathlib import Path

from railtracks.query import EventQuery, connect

_NAMESPACES = ["session", "node", "llm", "middleware"]


def _dir_mtime(events_dir: Path) -> float | None:
    """Newest mtime across ``events_dir/*.jsonl``, or ``None`` when empty."""
    files = list(events_dir.glob("*.jsonl"))
    if not files:
        return None
    return max(f.stat().st_mtime for f in files)


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
        self._scanned_mtime: float | None = None

    def get(self, events_dir: Path) -> EventQuery:
        mtime = _dir_mtime(events_dir)
        with self._lock:
            if self._query is None:
                self._query = connect(events_dir, _NAMESPACES)
                self._scanned_mtime = mtime
                return self._query
            if mtime != self._scanned_mtime:
                self._query.refresh()
                self._scanned_mtime = mtime
            return self._query

    def close(self) -> None:
        with self._lock:
            if self._query is not None:
                self._query.close()
                self._query = None
            self._scanned_mtime = None


_registry = _ConnectionRegistry()


def get_query(events_dir: Path) -> EventQuery:
    """Return the shared :class:`EventQuery`, refreshing when files change."""
    return _registry.get(events_dir)


def close_query() -> None:
    """Close the shared connection. Called from shutdown handlers and tests."""
    _registry.close()


atexit.register(close_query)
