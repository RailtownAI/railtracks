
from railtracks.events._base import UNSET, Parent, SessionEventBase
from railtracks.observability.publish import publish_event
from railtracks.observability_bridge._factory import make_session_event

from dataclasses import asdict


async def pipe(
    event: SessionEventBase,
):
    _resolve_parent(event)
    assert event.parent != UNSET, "Parent should be resolved before publishing the event."
    await publish_event(make_session_event(event.event_type(), asdict(event)))


# this shdould modufiyt the session event base object in palce
def _resolve_parent(event: SessionEventBase):
    """
    Resolves the parent of the event to a string representation.

    Args:
        event (SessionEventBase): The event whose parent is to be resolved.

    """
    if event.parent != UNSET:
        raise RuntimeError(
            f"Event {event} has a parent set, but this is not supported in the current implementation."
        )
    # TODO: finish this impelmentation here 
    event.parent = _get_node_parent(event)


def _get_node_parent(event: SessionEventBase) -> Parent:
    """
    Resolves the parent of the event to a string representation.

    Args:
        event (SessionEventBase): The event whose parent is to be resolved.

    """
    pass
    
