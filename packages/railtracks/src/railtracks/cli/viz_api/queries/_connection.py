"""DuckDB connection lifecycle for the visualizer query layer.

A single :class:`~railtracks.query.EventQuery` is kept alive for the life of
the process. Each request calls :func:`get_query`, which reopens the
connection on first use and after that only re-scans the ``*.jsonl`` files
when their newest mtime has moved. That keeps the per-request cost
proportional to the query, not to the file size — the file scan lands once
per write, not once per read.
"""

from __future__ import annotations

from pathlib import Path

from railtracks.query import EventQuery, connect

_NAMESPACES = ["session", "node", "llm", "middleware"]

_query: EventQuery | None = None
_scanned_mtime: float | None = None


def _dir_mtime(events_dir: Path) -> float | None:
    """Newest mtime across ``events_dir/*.jsonl``, or ``None`` when empty."""
    files = list(events_dir.glob("*.jsonl"))
    if not files:
        return None
    return max(f.stat().st_mtime for f in files)


def get_query(events_dir: Path) -> EventQuery:
    """Return a shared :class:`EventQuery`, refreshing when the source files change.

    First call opens the DuckDB connection and registers the four namespace
    views. Subsequent calls compare the newest ``*.jsonl`` mtime against the
    last scan and call ``refresh()`` only when it has moved.
    """
    global _query, _scanned_mtime
    mtime = _dir_mtime(events_dir)
    if _query is None:
        _query = connect(events_dir, _NAMESPACES)
        _scanned_mtime = mtime
        return _query
    if mtime != _scanned_mtime:
        _query.refresh()
        _scanned_mtime = mtime
    return _query


def close_query() -> None:
    """Close the shared connection. Called from shutdown handlers and tests."""
    global _query, _scanned_mtime
    if _query is not None:
        _query.close()
        _query = None
    _scanned_mtime = None
