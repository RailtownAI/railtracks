from __future__ import annotations

from mypy import scope
from railtracks.context.scope_link import ScopeLink
from railtracks.context.session_context import ScopeEntry, ScopeKind
from railtracks.events._base import LLMParent, LLMAndMiddlewareSpatialParent, NoSpatialParent, NodeParent, NodeSpatialParent, Parent, SpatialParent


# The two chain kinds that both denote "a node" (a node's boundary NODE entry and the
# NODE_BODY pushed on top of it during body execution).
_NODE_KINDS = frozenset({ScopeKind.NODE, ScopeKind.NODE_BODY})

def node_spatial_parent(scope: ScopeLink[ScopeEntry] | None):
    """Parent of a running node event (NodeInvocation/Response/Failure/Destruction)."""
    if scope is None:
        return NodeSpatialParent(node_id=None)
    
    # 2 levels up please
    node_link = scope.find_link(lambda e: e.kind is ScopeKind.NODE)

    if node_link is None or node_link.parent is None:
        return NodeSpatialParent(node_id=None)
    
    node_link = node_link.parent.find_link(lambda e: e.kind is ScopeKind.NODE) if scope is not None else None

    if node_link is None:
        return NodeSpatialParent(node_id=None)
    
    return NodeSpatialParent(node_id=node_link.value.id)


def node_parent(scope: ScopeLink[ScopeEntry] | None):
    assert scope is not None, "Expected a scope chain for node parent resolution"
    
    node_link = scope.find_link(lambda e: e.kind in _NODE_KINDS)
    assert node_link is not None, "Expected a node scope entry for node parent resolution"
        
    return NodeParent(node_id=node_link.value.id)


def llm_spatial_parent(scope: ScopeLink[ScopeEntry] | None):
    """Parent of an LLM event — the enclosing node (+ intervening middleware)."""
    node_link = scope.find_link(lambda e: e.kind in _NODE_KINDS) if scope is not None else None
    assert node_link is not None, "Expected a node scope entry for LLM spatial parent resolution"
    return NodeSpatialParent(node_id=node_link.value.id)



def llm_parent(scope: ScopeLink[ScopeEntry] | None):
    assert scope is not None, "Expected a scope chain for LLM parent resolution"
    curr_link = scope.find_link(lambda e: e.kind is ScopeKind.LLM)
    assert curr_link is not None, "Expected an LLM scope entry for LLM parent resolution"
    
    type_id = curr_link.value.type_id
    call_id = curr_link.value.id

    assert type_id is not None, "Expected an LLM scope entry with a type_id"

    return LLMParent(
        llm_model_id=type_id,
        llm_invoke_id=call_id,
    )


