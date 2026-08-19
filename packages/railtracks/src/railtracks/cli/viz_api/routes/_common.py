"""Shared helpers for the route modules."""

from __future__ import annotations

from pathlib import Path

from railtracks.paths import resolve_railtracks_home

_EVENTS_SUBDIR = "data/new-ones"

#: UUID-shape pattern applied to ``{session_id}`` so the sibling literals
#: ``/sessions/stats`` and ``/sessions/filters`` are not swallowed as ids.
_SESSION_ID_PATTERN = (
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _events_dir() -> Path:
    return resolve_railtracks_home() / _EVENTS_SUBDIR
