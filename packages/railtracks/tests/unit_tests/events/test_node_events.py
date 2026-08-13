"""Node event classes: event_type strings and parent-resolver dispatch."""

from railtracks.context.scope_link import ScopeLink
from railtracks.context.session_context import ScopeEntry, ScopeKind
from railtracks.events._base import NodeParent, NodeSpatialParent, NoSpatialParent
from railtracks.events.node import (
    NodeCreation,
    NodeDestruction,
    NodeFailure,
    NodeInvocation,
    NodeResponse,
)


def chain(*entries: tuple[ScopeKind, str]) -> ScopeLink[ScopeEntry] | None:
    link: ScopeLink[ScopeEntry] | None = None
    for kind, id_ in entries:
        e = ScopeEntry(kind, id_)
        link = ScopeLink(value=e) if link is None else link.pushed(e)
    return link


def test_event_type_strings():
    assert (
        NodeCreation(node_id="1", name="Agent", node_type="agent").event_type()
        == "node.creation"
    )
    assert NodeInvocation(args=(), kwargs={}).event_type() == "node.invocation"
    assert NodeResponse(response="r").event_type() == "node.response"
    assert NodeFailure(exception_name="boom", exception_message="boom").event_type() == "node.failure"
    assert (
        NodeDestruction(response="r", duration_seconds=0.0).event_type()
        == "node.destruction"
    )


def test_runtime_node_event_resolves_self_and_enclosing_node():
    # node "1" running under the caller's body → self is "1", nested inside "caller"
    scope = chain(
        (ScopeKind.NODE, "caller"),
        (ScopeKind.NODE_BODY, "caller"),
        (ScopeKind.NODE, "1"),
    )
    ev = NodeInvocation(args=(), kwargs={})
    ev.resolve_relationships(scope)

    assert ev.parent == NodeParent(node_id="1")
    assert ev.spatial_parent == NodeSpatialParent(node_id="caller")
    ev.verify()


def test_node_creation_has_no_spatial_parent():
    # a creation event is emitted before the node enters its own scope
    ev = NodeCreation(node_id="1", name="Agent", node_type="agent")
    assert ev._get_spatial_parent(None) == NoSpatialParent()
    assert (
        ev._get_spatial_parent(chain((ScopeKind.NODE, "caller"))) == NoSpatialParent()
    )
