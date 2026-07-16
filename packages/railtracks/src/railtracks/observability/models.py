from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

SCOPE_SESSION = "session"
SCOPE_RETRIEVAL = "retrieval"
SCOPE_EVALUATION = "evaluation"


class Timestamp:
    """Namespace helper for constructing `Event.stamp`. The field itself is a plain tz-aware UTC datetime."""

    # Doing it this way to make potential changes easier
    @staticmethod
    def now() -> datetime:
        return datetime.now(timezone.utc)


@dataclass
class Event:
    event_type: str
    scope_type: str
    scope_id: str
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    stamp: datetime = field(default_factory=Timestamp.now)
    parent_scope_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
