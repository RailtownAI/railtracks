"""Parent resolver tests — synthetic scope chains, one per design decision.

Chains are written bottom (root) → top, mirroring how the runtime pushes them
(`enter_node` first, `enter_node_body`/`enter_middleware`/`enter_llm_call` on top).
"""

import pytest
from railtracks.context.scope_link import ScopeLink
from railtracks.context.session_context import ScopeEntry, ScopeKind
from railtracks.events._base import LLMParent, NodeParent, NoParent
from railtracks.events._resolve import (
    llm_spatial_parent,
    middleware_parent,
    model_middleware_parent,
    node_creation_spatial_parent,
    node_spatial_parent,
)

N = ScopeKind.NODE
NB = ScopeKind.NODE_BODY
MW = ScopeKind.MIDDLEWARE
LLM = ScopeKind.LLM


def chain(*entries: tuple[ScopeKind, str]) -> ScopeLink[ScopeEntry] | None:
    """Build a chain from (kind, id) pairs given bottom (root) → top."""
    link: ScopeLink[ScopeEntry] | None = None
    for kind, id_ in entries:
        e = ScopeEntry(kind, id_)
        link = ScopeLink(value=e) if link is None else link.pushed(e)
    return link


# ── Node events (node_parent) ────────────────────────────────────────────────


def test_root_node_has_no_parent():
    # A is the root; nothing below its NODE entry
    assert node_spatial_parent(chain((N, "A"), (NB, "A"))) == NoParent()


def test_nested_node_resolves_to_caller_node():
    # B called from A's body
    scope = chain((N, "A"), (NB, "A"), (N, "B"), (NB, "B"))
    assert node_spatial_parent(scope) == NodeParent(node_id="A", middleware_id=None)


def test_node_called_from_a_middleware_collapses_to_nodeparent_with_mw():
    # B spawned from middleware m on A → NodeParent(A, mw=m), not MiddlewareParent
    scope = chain((N, "A"), (NB, "A"), (MW, "m"), (N, "B"), (NB, "B"))
    assert node_spatial_parent(scope) == NodeParent(node_id="A", middleware_id="m")


def test_nodes_own_middleware_does_not_leak_into_its_parent():
    # B's own middleware (bm) sits above NODE(B); it must not become the parent's mw hop
    scope = chain((N, "A"), (NB, "A"), (N, "B"), (MW, "bm"), (NB, "B"))
    assert node_spatial_parent(scope) == NodeParent(node_id="A", middleware_id=None)


def test_node_with_llm_in_ancestry_skips_llm_and_anchors_on_node():
    # C spawned by a model-middleware while A's LLM call is open.
    # chain bottom→top: NODE(A), NODE_BODY(A), LLM(l), MW(model-mw), NODE(C), NODE_BODY(C)
    scope = chain(
        (N, "A"), (NB, "A"), (LLM, "l"), (MW, "model-mw"), (N, "C"), (NB, "C")
    )
    parent = node_spatial_parent(scope)
    assert parent == NodeParent(node_id="A", middleware_id="model-mw")
    assert not isinstance(parent, LLMParent)  # LLM entry is transparent to a node event


def test_node_parent_raises_when_self_node_absent():
    # bad state: a node event with no NODE entry on the chain
    with pytest.raises(ValueError):
        node_spatial_parent(chain((MW, "m")))
    with pytest.raises(ValueError):
        node_spatial_parent(None)


# ── General middleware events (middleware_parent) ────────────────────────────


def test_middleware_parent_is_node_with_immediate_wrapper():
    # mw2 wraps mw1 on A → NodeParent(A, mw=mw1) (the middleware directly below self)
    scope = chain((N, "A"), (MW, "mw1"), (MW, "mw2"))
    assert middleware_parent(scope) == NodeParent(node_id="A", middleware_id="mw1")


def test_single_middleware_parent_has_no_intervening_mw():
    scope = chain((N, "A"), (MW, "mw1"))
    assert middleware_parent(scope) == NodeParent(node_id="A", middleware_id=None)


# ── Model-middleware events (model_middleware_parent) — anchor = LLM ─────────


def test_model_middleware_anchors_on_the_llm_call():
    scope = chain((N, "A"), (NB, "A"), (LLM, "l"), (MW, "model-mw"))
    assert model_middleware_parent(scope) == LLMParent(llm_id="l", middleware_id=None)


def test_nested_model_middleware_keeps_immediate_wrapper():
    scope = chain((N, "A"), (NB, "A"), (LLM, "l"), (MW, "mm1"), (MW, "mm2"))
    assert model_middleware_parent(scope) == LLMParent(llm_id="l", middleware_id="mm1")


# ── LLM events (llm_parent) ──────────────────────────────────────────────────


def test_llm_event_resolves_to_enclosing_node():
    scope = chain((N, "A"), (NB, "A"), (LLM, "l"))
    assert llm_spatial_parent(scope) == NodeParent(node_id="A", middleware_id=None)


# ── NodeCreation (node_creation_parent) — self not on chain ──────────────────


def test_node_creation_from_body_resolves_to_creating_node():
    # caller (A) chain is ambient; the new node is NOT on it
    assert node_creation_spatial_parent(chain((N, "A"), (NB, "A"))) == NodeParent(
        node_id="A", middleware_id=None
    )


def test_node_creation_at_root_has_no_parent():
    assert node_creation_spatial_parent(None) == NoParent()


def test_node_creation_from_middleware_records_the_middleware():
    scope = chain((N, "A"), (NB, "A"), (MW, "m"))
    assert node_creation_spatial_parent(scope) == NodeParent(node_id="A", middleware_id="m")
