from dataclasses import asdict

from railtracks.context.central import (
    LLMCallData,
    get_llm_call_id,
    get_middleware_id,
    get_node_or_llm,
    get_parent_id,
    get_parent_middleware_id,
)
from railtracks.events._base import (
    UNSET,
    LLMSpatialParent,
    NodeSpatialParent,
    NoSpatialParent,
    SessionEventBase,
    SpatialParent,
)
from railtracks.events.llm import LLMCreationEvent, LLMMessageBase, LLMParent
from railtracks.events.middleware import (
    MiddlewareCreationEvent,
    MiddlewareEventBase,
    MiddlewareParent,
)
from railtracks.observability.publish import publish_event
from railtracks.observability_bridge._factory import make_session_event


async def pipe(
    event: SessionEventBase,
):
    _resolve_parent(event)
    event.verify()

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
    elif isinstance(event, MiddlewareEventBase):
        spatial_parent, parent = _get_middleware_parents(event)
        event.spatial_parent = spatial_parent
        event.parent = parent
    elif isinstance(event, MiddlewareCreationEvent):
        spatial_parent = _get_middleware_creation_parents(event)
        event.spatial_parent = spatial_parent
    else:
        raise RuntimeError(f"Unknown event type {type(event)}")


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


def _get_middleware_parents(
    event: MiddlewareEventBase,
) -> tuple[NodeSpatialParent | LLMSpatialParent, MiddlewareParent]:
    parent = get_node_or_llm()
    parent_middleware = get_parent_middleware_id()

    middleware_id = parent_middleware.type_id if parent_middleware is not None else None

    assert parent is not None, (
        "Middleware must be called within a node or LLM context when publishing a middleware event."
    )

    p_link: NodeSpatialParent | LLMSpatialParent
    if isinstance(parent, LLMCallData):
        p_link = LLMSpatialParent(llm_id=parent.type_id, middleware_id=middleware_id)
    else:
        p_link = NodeSpatialParent(node_id=parent, middleware_id=middleware_id)

    middleware_item = get_middleware_id()

    assert middleware_item is not None, (
        "Middleware ID should be set in the context when publishing a middleware event."
    )

    actual_parent = MiddlewareParent(
        middleware_type_id=middleware_item.type_id,
        middleware_invoke_id=middleware_item.call_id,
    )

    return p_link, actual_parent


def _get_middleware_creation_parents(event: MiddlewareCreationEvent) -> NoSpatialParent:
    return NoSpatialParent()
