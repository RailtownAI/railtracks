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
from railtracks.events._base import (
    LLMAndMiddlewareSpatialParent,
    LLMParent,
    MiddlewareParent,
    MiddlewareSpatialParent,
    NodeAndMiddlewareSpatialParent,
    NodeParent,
    NodeSpatialParent,
)
from railtracks.events._resolve import (
    llm_parent,
    llm_spatial_parent,
    middleware_parent,
    middleware_spatial_parent,
    model_middleware_spatial_parent,
    node_parent,
    node_spatial_parent,
    regular_middleware_spatial_parent,
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


def test_node_called_directly_from_a_middleware_anchors_on_that_middleware():
    # B spawned from middleware m on A: the resolver stops at the nearest MIDDLEWARE
    # entry rather than continuing on to A. That's why NodeEventBase's spatial parent
    # type is `NodeSpatialParent | MiddlewareSpatialParent` — resolving the rest of
    # the way to the owning node is left to whoever consumes middleware m's own
    # parent chain, not to this resolver.
    scope = chain((N, "A"), (NB, "A"), (MW, "m", "mw-type"), (N, "B"), (NB, "B"))
    assert node_spatial_parent(scope) == MiddlewareSpatialParent(
        middleware_invoke_id="m"
    )


def test_nodes_own_middleware_does_not_shift_its_enclosing_node():
    # B's own middleware (bm) sits above NODE(B); it must not change what B is nested in
    scope = chain((N, "A"), (NB, "A"), (N, "B"), (MW, "bm", "mw-type"), (NB, "B"))
    assert node_spatial_parent(scope) == NodeSpatialParent(node_id="A")


def test_node_called_from_a_model_middleware_anchors_on_that_middleware():
    # C spawned by a model-middleware while A's LLM call is open: same rule as above
    # — the resolver anchors on the nearest MIDDLEWARE entry (model-mw), not on the
    # LLM call or node underneath it.
    scope = chain(
        (N, "A"),
        (NB, "A"),
        (LLM, "l", "llm-type"),
        (MW, "model-mw", "mw-type"),
        (N, "C"),
        (NB, "C"),
    )
    assert node_spatial_parent(scope) == MiddlewareSpatialParent(
        middleware_invoke_id="model-mw"
    )


def test_node_spatial_parent_matches_a_bare_node_entry_at_the_top():
    # NodeDestruction fires after middleware/body have unwound, so the scope top is
    # NODE(B) itself, not NODE_BODY(B). find_link is self-inclusive, so this must
    # still resolve rather than skipping past B to look for some ancestor NODE.
    scope = chain((N, "A"), (NB, "A"), (N, "B"))
    assert node_spatial_parent(scope) == NodeSpatialParent(node_id="A")


def test_node_spatial_parent_silently_returns_none_for_an_unhandled_parent_kind():
    # Malformed chain: B's NODE entry sits directly on another NODE entry, with no
    # NODE_BODY/MIDDLEWARE between them. The function only branches on NODE_BODY and
    # MIDDLEWARE parents; anything else (including this) falls through with no return
    # statement, i.e. returns None instead of raising. Documenting current behavior —
    # this looks like a latent gap rather than an intentional contract.
    scope = chain((N, "A"), (N, "B"))
    assert node_spatial_parent(scope) is None


# ── Node events: parent (self) ───────────────────────────────────────────────


def test_node_parent_is_self():
    scope = chain((N, "A"), (NB, "A"), (N, "B"), (NB, "B"))
    assert node_parent(scope) == NodeParent(node_id="B")


def test_node_parent_matches_a_bare_node_entry_at_the_top():
    # NodeDestruction-style scope: top is NODE(B), not NODE_BODY(B).
    scope = chain((N, "A"), (NB, "A"), (N, "B"))
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


def test_llm_event_matches_a_bare_node_entry_not_just_node_body():
    # _NODE_KINDS covers both NODE and NODE_BODY — exercise the NODE-only branch too.
    scope = chain((N, "A"), (LLM, "l", "llm-type"))
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


# ── Middleware events: parent (self) ─────────────────────────────────────────
#
# Unlike the other resolvers, `middleware_parent` does not search the chain — it
# requires the scope *top* to already be the middleware's own entry (that's how
# `_scoped()` in middleware/chain.py calls emit(): right after `enter_middleware`,
# before anything else is pushed).


def test_middleware_parent_is_the_top_entry():
    scope = chain((N, "A"), (MW, "m1", "mw-type"))
    assert middleware_parent(scope) == MiddlewareParent(
        middleware_type_id="mw-type", middleware_invoke_id="m1"
    )


def test_middleware_parent_raises_when_scope_is_none():
    with pytest.raises(AssertionError):
        middleware_parent(None)


def test_middleware_parent_raises_when_top_is_not_middleware():
    # bad state: called with a scope whose top entry isn't the middleware itself
    with pytest.raises(AssertionError):
        middleware_parent(chain((N, "A")))


def test_middleware_parent_raises_when_type_id_missing():
    # ScopeEntry.__post_init__ forbids constructing a real MIDDLEWARE entry without a
    # type_id, so this defensive assert is otherwise unreachable through normal
    # construction. Exercise it directly with a duck-typed stand-in, since
    # middleware_parent only ever reads .kind/.id/.type_id off the scope value.
    class _BadEntry:
        kind = ScopeKind.MIDDLEWARE
        id = "m1"
        type_id = None

    with pytest.raises(AssertionError):
        middleware_parent(ScopeLink(value=_BadEntry()))  # type: ignore[arg-type]


# ── Middleware events: spatial parent (general resolver) ────────────────────
#
# `middleware_spatial_parent` walks *up from `scope.parent`*, deliberately skipping
# the top entry (assumed to be the middleware's own MIDDLEWARE entry — see the
# "Skip the first entry" comment in _resolve.py). It records the nearest enclosing
# MIDDLEWARE id it passes through, then anchors on the first NODE or LLM entry.


def test_outermost_middleware_anchors_on_its_node_with_no_enclosing_middleware():
    # m1 sits directly on NODE(A) — no other middleware wraps it.
    scope = chain((N, "A"), (MW, "m1", "mw-type"))
    assert middleware_spatial_parent(scope) == NodeAndMiddlewareSpatialParent(
        node_id="A", middleware_invoke_id=None
    )


def test_nested_middleware_anchors_on_node_and_captures_its_immediate_wrapper():
    # m2 runs inside m1, both wrapping node A.
    scope = chain((N, "A"), (MW, "m1", "mw-type"), (MW, "m2", "mw-type"))
    assert middleware_spatial_parent(scope) == NodeAndMiddlewareSpatialParent(
        node_id="A", middleware_invoke_id="m1"
    )


def test_middleware_spatial_parent_only_captures_the_nearest_enclosing_middleware():
    # m3 runs inside m2 inside m1: only m2 (the immediate wrapper) is captured, not m1.
    scope = chain(
        (N, "A"), (MW, "m1", "mw-type"), (MW, "m2", "mw-type"), (MW, "m3", "mw-type")
    )
    assert middleware_spatial_parent(scope) == NodeAndMiddlewareSpatialParent(
        node_id="A", middleware_invoke_id="m2"
    )


def test_outermost_model_middleware_anchors_on_its_llm_call():
    # mm1 sits directly on the open LLM call, below any node body.
    scope = chain((N, "A"), (NB, "A"), (LLM, "l", "llm-type"), (MW, "mm1", "mw-type"))
    assert middleware_spatial_parent(scope) == LLMAndMiddlewareSpatialParent(
        llm_invoke_id="l", middleware_invoke_id=None
    )


def test_nested_model_middleware_anchors_on_llm_and_captures_its_wrapper():
    scope = chain(
        (N, "A"),
        (NB, "A"),
        (LLM, "l", "llm-type"),
        (MW, "mm1", "mw-type"),
        (MW, "mm2", "mw-type"),
    )
    assert middleware_spatial_parent(scope) == LLMAndMiddlewareSpatialParent(
        llm_invoke_id="l", middleware_invoke_id="mm1"
    )


def test_middleware_spatial_parent_blindly_skips_the_top_entry():
    # middleware_spatial_parent never checks scope.value.kind (contrast with
    # middleware_parent's explicit assert). Called with a non-middleware scope, it
    # still discards the top entry as if it were "self" and resolves from there —
    # documenting the caller-contract assumption rather than a validated guarantee.
    scope = chain((N, "A"), (NB, "A"))
    assert middleware_spatial_parent(scope) == NodeAndMiddlewareSpatialParent(
        node_id="A", middleware_invoke_id=None
    )


def test_middleware_spatial_parent_raises_when_scope_is_none():
    with pytest.raises(AssertionError):
        middleware_spatial_parent(None)


def test_middleware_spatial_parent_raises_when_chain_runs_out():
    # scope.parent is None immediately — nothing to resolve against.
    with pytest.raises(AssertionError):
        middleware_spatial_parent(chain((MW, "m1", "mw-type")))


def test_middleware_spatial_parent_raises_on_unexpected_node_body_in_ancestry():
    # Malformed chain: a middleware entry sitting directly on a NODE_BODY, with no
    # NODE/LLM below it. A middleware always wraps a NODE or LLM entry directly in
    # the real pipeline (NODE_BODY is only ever pushed *inside* the innermost
    # middleware), so encountering NODE_BODY while walking up is treated as a bug.
    scope = chain((N, "A"), (NB, "A"), (MW, "bad", "mw-type"))
    with pytest.raises(AssertionError):
        middleware_spatial_parent(scope)


# ── Middleware events: spatial parent (regular/model wrappers) ──────────────
#
# `regular_middleware_spatial_parent` and `model_middleware_spatial_parent` delegate
# to `middleware_spatial_parent` and assert the result matches the expected shape —
# node-anchored for "regular" (output/guard) middleware, LLM-anchored for "model"
# middleware. A mismatch means the event was resolved against the wrong kind of
# scope (e.g. a model-only event fired outside an open LLM call).


def test_regular_middleware_spatial_parent_returns_node_anchored_result():
    scope = chain((N, "A"), (MW, "m1", "mw-type"))
    assert regular_middleware_spatial_parent(scope) == NodeAndMiddlewareSpatialParent(
        node_id="A", middleware_invoke_id=None
    )


def test_regular_middleware_spatial_parent_raises_on_llm_anchored_result():
    scope = chain((N, "A"), (NB, "A"), (LLM, "l", "llm-type"), (MW, "mm1", "mw-type"))
    with pytest.raises(AssertionError):
        regular_middleware_spatial_parent(scope)


def test_model_middleware_spatial_parent_returns_llm_anchored_result():
    scope = chain((N, "A"), (NB, "A"), (LLM, "l", "llm-type"), (MW, "mm1", "mw-type"))
    assert model_middleware_spatial_parent(scope) == LLMAndMiddlewareSpatialParent(
        llm_invoke_id="l", middleware_invoke_id=None
    )


def test_model_middleware_spatial_parent_raises_on_node_anchored_result():
    scope = chain((N, "A"), (MW, "m1", "mw-type"))
    with pytest.raises(AssertionError):
        model_middleware_spatial_parent(scope)
