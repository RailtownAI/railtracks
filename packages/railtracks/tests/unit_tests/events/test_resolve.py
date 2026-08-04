"""Parent resolver tests — synthetic scope chains.

Chains are written bottom (root) → top, mirroring how the runtime pushes them
(`enter_node` first, `enter_node_body`/`enter_middleware`/`enter_llm_call` on top).

Two identities come off the chain: the **spatial parent** (what the emitting entity is
nested inside) and the **parent** (the emitting entity's own entry — for a node event
that is the node itself).
"""

import pytest
from railtracks.context.scope_link import ScopeLink
from railtracks.context.session_context import ScopeEntry, ScopeKind
from railtracks.events._base import LLMParent, NodeParent, NodeSpatialParent
from railtracks.events._resolve import (
    llm_parent,
    llm_spatial_parent,
    node_parent,
    node_spatial_parent,
)

N = ScopeKind.NODE
NB = ScopeKind.NODE_BODY
MW = ScopeKind.MIDDLEWARE
LLM = ScopeKind.LLM


def chain(*entries: tuple[ScopeKind, str] | tuple[ScopeKind, str, str]):
    """Build a chain from (kind, id[, type_id]) tuples given bottom (root) → top."""
    link: ScopeLink[ScopeEntry] | None = None
    for entry in entries:
        e = ScopeEntry(*entry)
        link = ScopeLink(value=e) if link is None else link.pushed(e)
    return link


# ── Node events: spatial parent (the enclosing node, two hops up) ─────────────


def test_root_node_has_no_enclosing_node():
    # A is the root; nothing below its NODE entry
    assert node_spatial_parent(chain((N, "A"), (NB, "A"))) == NodeSpatialParent(
        node_id=None
    )


def test_no_scope_at_all_has_no_enclosing_node():
    assert node_spatial_parent(None) == NodeSpatialParent(node_id=None)


def test_nested_node_resolves_to_caller_node():
    # B called from A's body
    scope = chain((N, "A"), (NB, "A"), (N, "B"), (NB, "B"))
    assert node_spatial_parent(scope) == NodeSpatialParent(node_id="A")


def test_node_called_from_a_middleware_still_anchors_on_the_owning_node():
    # B spawned from middleware m on A → A is the enclosing node (a middleware never
    # stands on its own; it always runs "on" a node)
    scope = chain((N, "A"), (NB, "A"), (MW, "m", "mw-type"), (N, "B"), (NB, "B"))
    assert node_spatial_parent(scope) == NodeSpatialParent(node_id="A")


def test_nodes_own_middleware_does_not_shift_its_enclosing_node():
    # B's own middleware (bm) sits above NODE(B); it must not change what B is nested in
    scope = chain((N, "A"), (NB, "A"), (N, "B"), (MW, "bm", "mw-type"), (NB, "B"))
    assert node_spatial_parent(scope) == NodeSpatialParent(node_id="A")


def test_node_with_llm_in_ancestry_skips_llm_and_anchors_on_node():
    # C spawned by a model-middleware while A's LLM call is open: the LLM entry is
    # transparent to a node event.
    scope = chain(
        (N, "A"),
        (NB, "A"),
        (LLM, "l", "llm-type"),
        (MW, "model-mw", "mw-type"),
        (N, "C"),
        (NB, "C"),
    )
    assert node_spatial_parent(scope) == NodeSpatialParent(node_id="A")


# ── Node events: parent (self) ───────────────────────────────────────────────


def test_node_parent_is_self():
    scope = chain((N, "A"), (NB, "A"), (N, "B"), (NB, "B"))
    assert node_parent(scope) == NodeParent(node_id="B")


def test_node_parent_raises_when_self_node_absent():
    # bad state: a node event with no NODE entry on the chain
    with pytest.raises(AssertionError):
        node_parent(chain((MW, "m", "mw-type")))
    with pytest.raises(AssertionError):
        node_parent(None)


# ── LLM events ───────────────────────────────────────────────────────────────


def test_llm_event_is_nested_in_the_enclosing_node():
    scope = chain((N, "A"), (NB, "A"), (LLM, "l", "llm-type"))
    assert llm_spatial_parent(scope) == NodeSpatialParent(node_id="A")


def test_llm_parent_is_the_open_llm_call():
    scope = chain((N, "A"), (NB, "A"), (LLM, "call-1", "model-abc"))
    assert llm_parent(scope) == LLMParent(
        llm_type_id="model-abc", llm_invoke_id="call-1"
    )


def test_llm_resolvers_raise_without_the_expected_entry():
    with pytest.raises(AssertionError):
        llm_spatial_parent(chain((LLM, "l", "llm-type")))  # no enclosing node
    with pytest.raises(AssertionError):
        llm_parent(chain((N, "A"), (NB, "A")))  # no open llm call
