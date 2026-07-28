"""Node event classes: event_type strings and parent-resolver dispatch."""

from railtracks.context.scope_link import ScopeLink
from railtracks.context.session_context import ScopeEntry, ScopeKind
from railtracks.events._base import NodeParent, NoParent
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


def _node_kwargs():
    return {"name": "Agent", "node_id": "1", "node_type": "agent"}


def test_event_type_strings():
    assert NodeCreation(**_node_kwargs()).event_type() == "node.creation"
    assert (
        NodeInvocation(**_node_kwargs(), args=(), kwargs={}).event_type()
        == "node.invocation"
    )
    assert NodeResponse(**_node_kwargs(), response="r").event_type() == "node.response"
    assert NodeFailure(**_node_kwargs(), failure="boom").event_type() == "node.failure"
    assert (
        NodeDestruction(**_node_kwargs(), response="r").event_type()
        == "node.destruction"
    )


def test_runtime_node_event_resolves_via_node_parent():
    # node "1" running under the caller's body → caller is the parent
    scope = chain(
        (ScopeKind.NODE, "caller"),
        (ScopeKind.NODE_BODY, "caller"),
        (ScopeKind.NODE, "1"),
    )
    ev = NodeInvocation(**_node_kwargs(), args=(), kwargs={})
    assert ev.resolve_parent(scope) == NodeParent(node_id="caller", middleware_id=None)


def test_node_creation_resolves_via_creation_parent():
    # self ("1") is NOT on the chain; caller's body is ambient (no self-skip)
    scope = chain((ScopeKind.NODE, "caller"), (ScopeKind.NODE_BODY, "caller"))
    ev = NodeCreation(**_node_kwargs())
    assert ev.resolve_parent(scope) == NodeParent(node_id="caller", middleware_id=None)


def test_root_node_creation_has_no_parent():
    assert NodeCreation(**_node_kwargs()).resolve_parent(None) == NoParent()
