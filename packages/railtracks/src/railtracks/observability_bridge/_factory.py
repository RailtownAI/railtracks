from __future__ import annotations

from typing import Any

from railtracks.context.central import get_session_id
from railtracks.observability import SCOPE_SESSION, Event


def make_event(event_type: str, payload: dict[str, Any]) -> Event:
    """Build an `Event` scoped to the currently active Session.
    Args:
        event_type: The type of the event, e.g. "node.create"
        payload: The event payload, a dictionary of arbitrary data
    Returns:
        An `Event` object scoped to the currently active Session.
    Raises `ContextError` if no Session is active
    """
    sid = get_session_id()
    assert sid is not None, "session_id is required inside an active Session"
    return Event(
        event_type=event_type,
        scope_type=SCOPE_SESSION,
        scope_id=sid,
        payload=payload,
    )
