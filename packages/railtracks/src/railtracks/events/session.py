from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from railtracks.context.scope_link import ScopeLink
from railtracks.context.session_context import ScopeEntry

from ._base import (
    NoSpatialParent,
    SessionEventBase,
)

SessionStatus = Literal["success", "failure"]

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def format_error(error: BaseException) -> str:
    """Stringify an exception for an event payload."""
    return _ANSI_ESCAPE.sub("", str(error))


@dataclass(kw_only=True)
class SessionEventFamilyBase(SessionEventBase[NoSpatialParent]):
    """A session event is the root of the event tree.

    It is emitted outside of any node/middleware/llm scope, so there is nothing above
    it in the chain to resolve: neither a spatial parent nor a parent.
    """

    session_id: str

    def _get_spatial_parent(self, scope: ScopeLink[ScopeEntry] | None):
        return NoSpatialParent()


@dataclass(kw_only=True)
class SessionStarted(SessionEventFamilyBase):
    """A top-level run has begun. Carries the session identity plus the effective
    configuration the run will execute under."""

    flow_name: str | None
    flow_id: str | None
    session_name: str | None
    entry_point_name: str
    timeout: float | None
    end_on_error: bool
    save_state: bool

    def event_type(self) -> str:
        return "session.started"


@dataclass(kw_only=True)
class SessionCompleted(SessionEventFamilyBase):
    """A top-level run has finished, successfully or otherwise. `error` is a
    stringified exception and is only set when `status` is `"failure"`."""

    status: SessionStatus
    error: str | None
    duration_seconds: float

    def event_type(self) -> str:
        return "session.completed"
