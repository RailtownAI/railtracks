from __future__ import annotations

from railtracks.context.scope_link import ScopeLink
from railtracks.context.session_context import ScopeEntry, ScopeKind
from railtracks.events._base import LLMParent, LLMSpatialParent, NoSpatialParent, NodeParent, NodeSpatialParent, Parent, SpatialParent


# The two chain kinds that both denote "a node" (a node's boundary NODE entry and the
# NODE_BODY pushed on top of it during body execution).
_NODE_KINDS = frozenset({ScopeKind.NODE, ScopeKind.NODE_BODY})


def _parent_from_anchor(entry: ScopeEntry, middleware_id: str | None) -> SpatialParent:
    """Build the `Parent` for a matched anchor entry (+ its intervening middleware)."""
    if entry.kind in _NODE_KINDS:
        return NodeSpatialParent(node_id=entry.id, middleware_id=middleware_id)
    if entry.kind is ScopeKind.LLM:
        return LLMSpatialParent(llm_id=entry.id, middleware_id=middleware_id)
    raise ValueError(f"Cannot build a Parent from anchor scope kind {entry.kind!r}")


def _walk_for_parent(
    link: ScopeLink[ScopeEntry] | None,
    anchor_kinds: frozenset[ScopeKind],
) -> SpatialParent:
    """Walk down from `link`, capturing the first MIDDLEWARE as the intervening hop and
    stopping at the first entry whose kind is in `anchor_kinds`. Every other kind — including
    LLM when it is not an anchor — is transparent. Returns `NoParent` if the chain ends with
    no anchor found (the root)."""
    middleware_id: str | None = None
    while link is not None:
        entry = link.value
        if entry.kind is ScopeKind.MIDDLEWARE and middleware_id is None:
            middleware_id = entry.id
        elif entry.kind in anchor_kinds:
            return _parent_from_anchor(entry, middleware_id)
        link = link.parent

    return NoSpatialParent()


def resolve_parent(
    scope: ScopeLink[ScopeEntry] | None,
    *,
    self_kind: ScopeKind,
    anchor_kinds: frozenset[ScopeKind],
) -> SpatialParent:
    """Resolve the parent for an event whose *self* scope entry is on the chain.

    Locates self's own entry (the topmost of `self_kind`) and walks strictly below it. A
    missing self entry is bad state (the event was emitted from the wrong place) and raises —
    the first line of defense for a broken emission site.
    """
    self_link = (
        scope.find_link(lambda e: e.kind is self_kind) if scope is not None else None
    )

    if self_link is None:
        raise ValueError(
            f"Expected a {self_kind!r} scope entry for the emitting event, found none"
        )
    return _walk_for_parent(self_link.parent, anchor_kinds)


def resolve_parent_at_creation(
    scope: ScopeLink[ScopeEntry] | None,
    *,
    anchor_kinds: frozenset[ScopeKind],
) -> SpatialParent:
    """Resolve the parent for an event whose *self* is not on the chain yet (`NodeCreation`).
    Walks from the current top with no self-skip; the caller supplies self separately."""
    return _walk_for_parent(scope, anchor_kinds)


# ── Family resolvers ─────────────────────────────────────────────────────────────────────
# Thin wrappers pinning (self_kind, anchor_kinds) per event family. The bridge dispatches an
# event to the matching one; each is independently unit-tested against synthetic chains.


def node_spatial_parent(scope: ScopeLink[ScopeEntry] | None) -> NodeSpatialParent | NoSpatialParent:
    """Parent of a running node event (NodeInvocation/Response/Failure/Destruction)."""
    result = resolve_parent(scope, self_kind=ScopeKind.NODE, anchor_kinds=_NODE_KINDS)
    assert isinstance(result, (NodeSpatialParent, NoSpatialParent)), (
        f"Expected NodeSpatialParent or NoSpatialParent, got {type(result).__name__}"
    )
    return result

def node_creation_spatial_parent(scope: ScopeLink[ScopeEntry] | None) -> NoSpatialParent:
    """Parent of a `NodeCreation` event (self not yet on the chain)."""
    return NoSpatialParent()

def node_parent(scope: ScopeLink[ScopeEntry] | None) -> NodeParent:
    assert scope is not None, "Expected a scope chain for node parent resolution"
    assert scope.value.kind in _NODE_KINDS, (
        f"Expected a node scope entry for node parent resolution, got {scope.value.kind!r}"
    )

    return NodeParent(node_id=scope.value.id)


def llm_spatial_parent(scope: ScopeLink[ScopeEntry] | None) -> NodeSpatialParent:
    """Parent of an LLM event — the enclosing node (+ intervening middleware)."""
    result = resolve_parent(scope, self_kind=ScopeKind.LLM, anchor_kinds=_NODE_KINDS)
    assert isinstance(result, NodeSpatialParent), (
        f"Expected NodeSpatialParent, got {type(result).__name__}"
    )
    return result

def llm_creation_spatial_parent(scope: ScopeLink[ScopeEntry] | None) -> NoSpatialParent:
    """Parent of an LLM creation event (self not yet on the chain)."""
    return NoSpatialParent()

def llm_parent(scope: ScopeLink[ScopeEntry] | None) -> LLMParent:
    assert scope is not None, "Expected a scope chain for LLM parent resolution"
    curr_link = scope

    while True:
        assert curr_link is not None, "Expected an LLM scope entry for LLM parent resolution"
        if curr_link.value.kind is ScopeKind.LLM:
            break
        
        curr_link = curr_link.parent

    type_id = curr_link.value.type_id
    call_id = curr_link.value.id

    assert type_id is not None, "Expected an LLM scope entry with a type_id"

    return LLMParent(
        llm_model_id=type_id,
        llm_invoke_id=call_id,
    )


