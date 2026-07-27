from dataclasses import asdict

from railtracks.context.central import get_llm_call_id, get_parent_id
from railtracks.events._base import (
    UNSET,
    NodeSpatialParent,
    NoSpatialParent,
    SessionEventBase,
    SpatialParent,
)
from railtracks.events.llm import LLMCreationEvent, LLMMessageBase, LLMParent
from railtracks.observability.publish import publish_event
from railtracks.observability_bridge._factory import make_session_event


async def pipe(
    event: SessionEventBase,
):
    _resolve_parent(event)
    event.verify()

    print(asdict(event))

    await publish_event(make_session_event(event.event_type(), asdict(event)))


# this should modify the session event base object in place
def _resolve_parent(event: SessionEventBase):
    """
    Resolves the parent of the event to a string representation.

    Args:
        event (SessionEventBase): The event whose parent is to be resolved.

    """
    if event.spatial_parent != UNSET:
        raise RuntimeError(
            f"Event {event} has a parent set, but this is not supported in the current implementation."
        )
    if isinstance(event, LLMMessageBase):
        spatial_parent, parent = _get_llm_parents(event)
        event.spatial_parent = spatial_parent
        event.parent = parent
    elif isinstance(event, LLMCreationEvent):
        spatial_parent = _get_llm_creation_parents(event)
        event.spatial_parent = spatial_parent


def _get_node_parent(event: SessionEventBase) -> SpatialParent:
    """
    Resolves the parent of the event to a string representation.

    Args:
        event (SessionEventBase): The event whose parent is to be resolved.

    """
    pass


def _get_llm_parents(event: LLMMessageBase) -> tuple[NodeSpatialParent, LLMParent]:
    llm_call_details = get_llm_call_id()
    node_id = get_parent_id()

    # currently we do not support publishing LLM events outsiide of a node context. This is intentionally defensive.
    assert llm_call_details is not None, (
        "LLM call ID should be set in the context when publishing an LLM event."
    )
    assert node_id is not None, (
        "Node ID should be set in the context when publishing an LLM event."
    )

    return NodeSpatialParent(node_id), LLMParent(
        llm_invoke_id=llm_call_details.call_id, llm_model_id=llm_call_details.type_id
    )


def _get_llm_creation_parents(event: LLMCreationEvent) -> NoSpatialParent:
    return NoSpatialParent()
