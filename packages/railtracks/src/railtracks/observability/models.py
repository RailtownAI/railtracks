from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

SCOPE_SESSION = "session"
SCOPE_RETRIEVAL = "retrieval"
SCOPE_EVALUATION = "evaluation"


class Stamp:
    """Namespace helper for constructing `Event.stamp`. The field itself is a plain tz-aware UTC datetime."""

    # Doing it this way to make potential changes easier
    @staticmethod
    def now() -> datetime:
        return datetime.now(timezone.utc)


class Event(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    stamp: datetime
    scope_type: str
    scope_id: str
    parent_scope_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
