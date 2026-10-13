from __future__ import annotations

from railtracks.context.central import get_current_scope
from railtracks.events._base import (
    SessionEventBase,
)
from railtracks.observability.publish import publish_event, publish_event_nowait
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
        logger.exception(
            "observability: failed to emit %s", type(event).__name__, exc_info=True
        )


async def pipe(event: SessionEventBase) -> None:
    """Resolve the event's parent from the current scope chain, then publish it.

    Payload values are passed through as raw objects; the resolved `Parent`, the
    `datetime` timestamp, and node args/response are handed off untouched.
    """
    event.resolve_relationships(get_current_scope())
    event.verify()

    await publish_event(make_session_event(event.event_type(), event.encode()))


def emit_nowait(event: SessionEventBase) -> None:
    """Sync counterpart of `emit`, callable from any thread.

    The parent is resolved on the calling thread, so the event records the scope it
    happened in; only delivery is handed to the observer's loop.
    """
    try:
        event.resolve_relationships(get_current_scope())
        event.verify()
        publish_event_nowait(make_session_event(event.event_type(), event.encode()))
    except Exception:  # noqa: BLE001 - observability must not crash a node
        logger.exception(
            "observability: failed to emit %s", type(event).__name__, exc_info=True
        )
