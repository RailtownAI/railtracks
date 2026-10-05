"""Decision event classes: event_type strings, parent resolution and registry columns."""

from railtracks.context.scope_link import ScopeLink
from railtracks.context.session_context import ScopeEntry, ScopeKind
from railtracks.events._base import NodeParent, NodeSpatialParent
from railtracks.events.decision import (
    DecisionFailureEvent,
    DecisionInvocationEvent,
    DecisionResponseEvent,
)
from railtracks.events.registry import ColumnKind, payload_columns


def chain(*entries: tuple[ScopeKind, str]) -> ScopeLink[ScopeEntry] | None:
    link: ScopeLink[ScopeEntry] | None = None
    for kind, id_ in entries:
        type_id = f"{id_}_type" if kind is ScopeKind.MIDDLEWARE else None
        e = ScopeEntry(kind, id_, type_id)
        link = ScopeLink(value=e) if link is None else link.pushed(e)
    return link


def _invocation() -> DecisionInvocationEvent:
    return DecisionInvocationEvent(
        decision_id="d1",
        model_name="jev-latest",
        api_base="https://api.typesafe.ai",
        state="Help!",
        questions={"is_urgent": {"type": "noul", "instructions": "Urgent?"}},
    )


def test_event_type_strings():
    assert _invocation().event_type() == "decision.invocation"
    assert (
        DecisionResponseEvent(
            decision_id="d1",
            model_name="jev-latest",
            reported_model_name="jev-1.13.0",
            provider=None,
            answers={"is_urgent": {"noul": 0.9}},
            input_tokens=10,
            output_tokens=2,
            total_cost=None,
            latency=0.1,
        ).event_type()
        == "decision.response"
    )
    assert (
        DecisionFailureEvent(
            decision_id="d1",
            model_name="jev-latest",
            exception_name="E",
            exception_message="m",
        ).event_type()
        == "decision.failure"
    )


def test_resolves_to_the_enclosing_node_not_its_caller():
    scope = chain(
        (ScopeKind.NODE, "caller"),
        (ScopeKind.NODE_BODY, "caller"),
        (ScopeKind.NODE, "decider"),
        (ScopeKind.NODE_BODY, "decider"),
    )
    ev = _invocation()
    ev.resolve_relationships(scope)

    assert ev.parent == NodeParent(node_id="decider")
    assert ev.spatial_parent == NodeSpatialParent(node_id="decider")
    ev.verify()


def test_resolves_through_middleware_to_the_node():
    scope = chain(
        (ScopeKind.NODE, "decider"),
        (ScopeKind.MIDDLEWARE, "guard"),
    )
    ev = _invocation()
    ev.resolve_relationships(scope)

    assert ev.parent == NodeParent(node_id="decider")
    assert ev.spatial_parent == NodeSpatialParent(node_id="decider")


def test_registry_columns():
    cols = payload_columns("decision")
    for key in ("state", "questions", "answers"):
        assert cols[key].kind == ColumnKind.JSON
    for key in ("decision_id", "model_name", "reported_model_name", "provider"):
        assert cols[key].kind == ColumnKind.STRING
    for key in ("input_tokens", "output_tokens"):
        assert cols[key].kind == ColumnKind.INTEGER
    for key in ("total_cost", "latency"):
        assert cols[key].kind == ColumnKind.FLOAT
    assert cols["parent_node_id"].kind == ColumnKind.STRING
    assert cols["exception_message"].kind == ColumnKind.STRING
