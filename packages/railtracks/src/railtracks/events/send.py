"""Emission entry point: resolve an event's parent from the ambient scope, then publish it.

The full resolved `Parent` is carried in the event payload (with a `type` discriminator);
`Event.parent_scope_id` belongs to the observability scope model and is not set here.
"""

from __future__ import annotations

import datetime
from dataclasses import asdict, is_dataclass
from typing import Any

from railtracks.context.central import get_current_scope
from railtracks.events._base import UNSET, Parent, SessionEventBase
from railtracks.observability.publish import publish_event
from railtracks.observability_bridge._factory import make_session_event
from railtracks.utils.logging.create import get_rt_logger

logger = get_rt_logger(__name__)


async def emit(event: SessionEventBase) -> None:
    """Emit an event from the hot path, swallowing any failure.

    Observability must never break execution: if no session/observer is active, or
    resolution/publishing raises, we log at debug and carry on.
    """
    try:
        await pipe(event)
    except Exception:  # noqa: BLE001 - observability must not crash a node
        logger.debug(
            "observability: failed to emit %s", type(event).__name__, exc_info=True
        )


async def pipe(event: SessionEventBase) -> None:
    """Resolve the event's parent from the current scope chain, then publish it."""
    if event.parent is UNSET:
        event.parent = event.resolve_parent(get_current_scope())

    payload = _json_safe(asdict(event))
    payload["parent"] = _serialize_parent(event.parent)
    await publish_event(make_session_event(event.event_type(), payload))


def _serialize_parent(parent: Parent) -> dict[str, Any]:
    """Serialize a `Parent` with a `type` discriminator (asdict alone drops the class)."""
    fields = asdict(parent) if is_dataclass(parent) else {}
    return {"type": type(parent).__name__, **fields}


def _json_safe(value: Any) -> Any:
    """Placeholder serializer: coerce a payload into JSON-native types.

    `datetime` -> ISO string; anything not natively serializable -> `repr`. A richer
    serialization strategy (which fields to keep/drop, structured error capture) is a
    separate follow-up.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    return repr(value)
