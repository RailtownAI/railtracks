"""Filesystem locations shared by event producers and consumers."""

from __future__ import annotations

import os
from pathlib import Path

from railtracks.paths import resolve_railtracks_home

EVENTS_DIR_ENV = "RAILTRACKS_EVENTS_DIR"
EVENTS_SUBDIR = Path("data/events")


def resolve_events_dir() -> Path:
    """Return the JSONL event store used by the observer and visualizer.

    ``RAILTRACKS_EVENTS_DIR`` may point at an alternate store for development,
    imports, or tests. Relative overrides are resolved from the current working
    directory; without one, events live under the resolved Railtracks home.
    """
    override = os.environ.get(EVENTS_DIR_ENV)
    if override:
        return Path(override).expanduser().resolve()
    return resolve_railtracks_home() / EVENTS_SUBDIR
