from __future__ import annotations

from railtracks.context.scope_link import ScopeLink
from railtracks.context.session_context import ScopeEntry, ScopeKind
from railtracks.events._base import (
    LLMAndMiddlewareSpatialParent,
    LLMParent,
    MiddlewareParent,
    MiddlewareSpatialParent,
    NodeAndMiddlewareSpatialParent,
    NodeParent,
    NodeSpatialParent,
)

# The two chain kinds that both denote "a node" (a node's boundary NODE entry and the
# NODE_BODY pushed on top of it during body execution).
_NODE_KINDS = frozenset({ScopeKind.NODE, ScopeKind.NODE_BODY})


def node_spatial_parent(scope: ScopeLink[ScopeEntry] | None):
    """Parent of a running node event (NodeInvocation/Response/Failure/Destruction)."""
    if scope is None:
        return NodeSpatialParent(node_id=None)

    # first we need to traverse up to find the parent
    node_link = scope.find_link(lambda e: e.kind is ScopeKind.NODE)

    assert node_link is not None, (
        "Expected a node scope entry for node spatial parent resolution"
    )

    parent = node_link.parent

    # there are 3 cases here
    # 1. This is the top level node, so it has no parent
    if parent is None:
        return NodeSpatialParent(node_id=None)

    # 2. the node is called by another node
    if parent.value.kind is ScopeKind.NODE_BODY:
        return NodeSpatialParent(node_id=parent.value.id)

    # 3. the node is called by a middleware
    if parent.value.kind is ScopeKind.MIDDLEWARE:
        return MiddlewareSpatialParent(middleware_invoke_id=parent.value.id)

    # 2 levels up please
    node_link = scope.find_link(lambda e: e.kind is ScopeKind.NODE)

    if node_link is None or node_link.parent is None:
        return NodeSpatialParent(node_id=None)

    node_link = (
        node_link.parent.find_link(lambda e: e.kind is ScopeKind.NODE)
        if scope is not None
        else None
    )

    if node_link is None:
        return NodeSpatialParent(node_id=None)

    return NodeSpatialParent(node_id=node_link.value.id)


def node_parent(scope: ScopeLink[ScopeEntry] | None):
    assert scope is not None, "Expected a scope chain for node parent resolution"

    node_link = scope.find_link(lambda e: e.kind in _NODE_KINDS)
    assert node_link is not None, (
        "Expected a node scope entry for node parent resolution"
    )

    return NodeParent(node_id=node_link.value.id)


def llm_spatial_parent(scope: ScopeLink[ScopeEntry] | None):
    """Parent of an LLM event — the enclosing node (+ intervening middleware)."""
    node_link = (
        scope.find_link(lambda e: e.kind in _NODE_KINDS) if scope is not None else None
    )
    assert node_link is not None, (
        "Expected a node scope entry for LLM spatial parent resolution"
    )
    return NodeSpatialParent(node_id=node_link.value.id)


def llm_parent(scope: ScopeLink[ScopeEntry] | None):
    assert scope is not None, "Expected a scope chain for LLM parent resolution"
    curr_link = scope.find_link(lambda e: e.kind is ScopeKind.LLM)
    assert curr_link is not None, (
        "Expected an LLM scope entry for LLM parent resolution"
    )

    type_id = curr_link.value.type_id
    call_id = curr_link.value.id

    assert type_id is not None, "Expected an LLM scope entry with a type_id"

    return LLMParent(
        llm_type_id=type_id,
        llm_invoke_id=call_id,
    )


def middleware_parent(scope: ScopeLink[ScopeEntry] | None):
    assert scope is not None, "Expected a scope chain for middleware parent resolution"
    assert scope.value.kind == ScopeKind.MIDDLEWARE, (
        "Expected a middleware scope entry for middleware parent resolution"
    )
    assert scope.value.type_id is not None, (
        "Expected a middleware scope entry with a type_id"
    )

    return MiddlewareParent(
        middleware_type_id=scope.value.type_id,
        middleware_invoke_id=scope.value.id,
    )


def model_middleware_spatial_parent(scope: ScopeLink[ScopeEntry] | None):
    """Parent of a model middleware event — the enclosing node (+ intervening middleware)."""
    result = middleware_spatial_parent(scope)

    assert isinstance(result, LLMAndMiddlewareSpatialParent), (
        "Expected a model middleware spatial parent to be an LLMAndMiddlewareSpatialParent"
    )
    return result


def regular_middleware_spatial_parent(scope: ScopeLink[ScopeEntry] | None):
    """Parent of a regular middleware event — the enclosing node (+ intervening middleware)."""
    result = middleware_spatial_parent(scope)

    assert isinstance(result, NodeAndMiddlewareSpatialParent), (
        "Expected a regular middleware spatial parent to be a NodeAndMiddlewareSpatialParent"
    )
    return result


def middleware_spatial_parent(scope: ScopeLink[ScopeEntry] | None):
    """Parent of a regular middleware event — the enclosing node (+ intervening middleware)."""
    assert scope is not None, (
        "Expected a scope chain for model middleware spatial parent resolution"
    )
    link = scope.parent

    # Skip the first entry
    middleware_invoke_id: str | None = None

    while True:
        assert link is not None, (
            "Expected a scope chain for model middleware spatial parent resolution"
        )
        if link.value.kind == ScopeKind.MIDDLEWARE and middleware_invoke_id is None:
            middleware_invoke_id = link.value.id

        if link.value.kind == ScopeKind.NODE:
            return NodeAndMiddlewareSpatialParent(
                node_id=link.value.id,
                middleware_invoke_id=middleware_invoke_id,
            )

        if link.value.kind == ScopeKind.LLM:
            return LLMAndMiddlewareSpatialParent(
                llm_invoke_id=link.value.id,
                middleware_invoke_id=middleware_invoke_id,
            )

        assert not link.value.kind == ScopeKind.NODE_BODY, (
            "Unexpected NODE_BODY scope entry for model middleware spatial parent resolution"
        )

        link = link.parent
