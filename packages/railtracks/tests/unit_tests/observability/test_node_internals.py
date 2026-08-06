"""The fold from session events back to the legacy `details.internals` block."""

import pytest
from railtracks.guardrails.core.decision import GuardrailDecision
from railtracks.observability import Event, NodeInternalsCollector

SESSION = "sess-1"
AGENT = "node-agent"
TOOL = "node-tool"
LLM_CALL = "llm-invoke-1"
GUARD_MW = "mw-type-guard"


def _event(event_type: str, **payload) -> Event:
    return Event(
        event_type=event_type,
        scope_type="session",
        scope_id=SESSION,
        payload=payload,
    )


def _node_creation(node_id: str, name: str, node_type: str) -> Event:
    return _event("node.creation", node_id=node_id, name=name, node_type=node_type)


def _node_destruction(node_id: str, duration: float) -> Event:
    # a node event's `parent` is the node itself
    return _event("node.destruction", parent_node_id=node_id, duration_seconds=duration)


def _llm_response(node_id: str, **overrides) -> Event:
    payload = {
        "spatial_parent_node_id": node_id,
        "parent_llm_invoke_id": LLM_CALL,
        "message_input": ["in"],
        "output": "out",
        "model_name": "claude-sonnet-4-6",
        "model_provider": "Anthropic",
        "input_tokens": 10,
        "output_tokens": 5,
        "total_cost": 0.001,
        "system_fingerprint": None,
        "latency": 1.5,
    }
    payload.update(overrides)
    return _event("llm.response", **payload)


def _collect(*events: Event) -> NodeInternalsCollector:
    collector = NodeInternalsCollector()
    for event in events:
        collector.record(event)
    return collector


async def test_llm_node_gets_the_legacy_three_key_block():
    collector = _collect(
        _node_creation(AGENT, "My-Agent", "Agent"),
        _llm_response(AGENT),
        _node_destruction(AGENT, 2.5),
    )

    block = collector.internals_for(SESSION)[AGENT]
    assert list(block) == ["guard_details", "llm_details", "latency"]
    assert block["latency"] == {"total_time": 2.5}
    assert block["guard_details"] == []
    assert block["llm_details"] == [
        {
            "model_name": "claude-sonnet-4-6",
            "model_provider": "Anthropic",
            "input": ["in"],
            "output": "out",
            "input_tokens": 10,
            "output_tokens": 5,
            "total_cost": 0.001,
            "system_fingerprint": None,
            "latency": 1.5,
        }
    ]


async def test_tool_node_gets_latency_only():
    """A function node had no LLM keys at all, not empty ones."""
    collector = _collect(
        _node_creation(TOOL, "my_tool", "Tool"),
        _node_destruction(TOOL, 0.25),
    )

    assert collector.internals_for(SESSION)[TOOL] == {"latency": {"total_time": 0.25}}


async def test_agent_with_no_llm_calls_still_reports_empty_lists():
    """LLMBase seeded both lists in __init__, so a node that never called reports []."""
    collector = _collect(
        _node_creation(AGENT, "My-Agent", "Agent"),
        _node_destruction(AGENT, 0.1),
    )

    block = collector.internals_for(SESSION)[AGENT]
    assert block["llm_details"] == []
    assert block["guard_details"] == []


async def test_llm_details_preserve_call_order():
    """The visualizer reads llm_details[-1] as the node's headline model."""
    collector = _collect(
        _node_creation(AGENT, "My-Agent", "Agent"),
        _llm_response(AGENT, model_name="first"),
        _llm_response(AGENT, model_name="second"),
        _llm_response(AGENT, model_name="third"),
    )

    names = [
        c["model_name"] for c in collector.internals_for(SESSION)[AGENT]["llm_details"]
    ]
    assert names == ["first", "second", "third"]


async def test_llm_failure_becomes_an_entry_with_a_null_output():
    collector = _collect(
        _node_creation(AGENT, "My-Agent", "Agent"),
        _event(
            "llm.failure",
            spatial_parent_node_id=AGENT,
            parent_llm_invoke_id=LLM_CALL,
            message_input=["in"],
            model_name="claude-sonnet-4-6",
            model_provider="Anthropic",
            exception_name="RuntimeError",
            exception_message="boom",
        ),
    )

    entry = collector.internals_for(SESSION)[AGENT]["llm_details"][0]
    assert entry["output"] is None
    assert entry["input_tokens"] is None
    assert entry["model_name"] == "claude-sonnet-4-6"


async def test_guard_traces_attach_to_the_node_that_made_the_call():
    """Guard events name an LLM invocation, not a node; the join goes through it."""
    collector = _collect(
        _node_creation(AGENT, "My-Agent", "Agent"),
        _event(
            "middleware.creation",
            middleware_type_id=GUARD_MW,
            middleware_name="no_profanity",
        ),
        _event(
            "middleware.guard.input.response",
            spatial_parent_llm_invoke_id=LLM_CALL,
            parent_middleware_type_id=GUARD_MW,
            decision=GuardrailDecision.allow(reason="clean", meta={"hits": 0}),
        ),
        _llm_response(AGENT),
    )

    traces = collector.internals_for(SESSION)[AGENT]["guard_details"]
    assert traces == [
        {
            "rail_name": "no_profanity",
            "phase": "llm_input",
            "action": "allow",
            "reason": "clean",
            "meta": {"hits": 0},
        }
    ]


async def test_guard_failure_becomes_an_error_trace():
    collector = _collect(
        _node_creation(AGENT, "My-Agent", "Agent"),
        _event(
            "middleware.creation",
            middleware_type_id=GUARD_MW,
            middleware_name="no_profanity",
        ),
        _llm_response(AGENT),
        _event(
            "middleware.guard.output.failure",
            spatial_parent_llm_invoke_id=LLM_CALL,
            parent_middleware_type_id=GUARD_MW,
            exception_name="ValueError",
            exception_message="rail blew up",
        ),
    )

    trace = collector.internals_for(SESSION)[AGENT]["guard_details"][0]
    assert trace["action"] == "error"
    assert trace["phase"] == "llm_output"
    assert trace["meta"] == {
        "exception_type": "ValueError",
        "exception_message": "rail blew up",
    }


async def test_guard_event_before_its_llm_event_still_resolves():
    """Ordering-independence: the input rail runs before the call it guards."""
    collector = _collect(
        _node_creation(AGENT, "My-Agent", "Agent"),
        _event(
            "middleware.creation",
            middleware_type_id=GUARD_MW,
            middleware_name="no_profanity",
        ),
        # arrives first, and nothing yet says which node owns LLM_CALL
        _event(
            "middleware.guard.input.response",
            spatial_parent_llm_invoke_id=LLM_CALL,
            parent_middleware_type_id=GUARD_MW,
            decision=GuardrailDecision.allow(reason="clean"),
        ),
        _event(
            "llm.invocation",
            spatial_parent_node_id=AGENT,
            parent_llm_invoke_id=LLM_CALL,
            message_input=["in"],
        ),
    )

    assert len(collector.internals_for(SESSION)[AGENT]["guard_details"]) == 1


async def test_sessions_are_kept_apart():
    collector = NodeInternalsCollector()
    collector.record(_node_creation(AGENT, "My-Agent", "Agent"))
    other = Event(
        event_type="node.creation",
        scope_type="session",
        scope_id="sess-2",
        payload={"node_id": "other-node", "name": "Other", "node_type": "Agent"},
    )
    collector.record(other)

    assert set(collector.internals_for(SESSION)) == {AGENT}
    assert set(collector.internals_for("sess-2")) == {"other-node"}


async def test_unknown_session_is_empty_rather_than_an_error():
    collector = NodeInternalsCollector()
    assert collector.internals_for("never-seen") == {}


async def test_irrelevant_events_are_not_retained():
    collector = _collect(
        _event("session.started", session_id=SESSION),
        _event("middleware.model.invocation", message_history=["x"]),
    )
    assert collector.internals_for(SESSION) == {}


async def test_discard_frees_a_session():
    collector = _collect(_node_creation(AGENT, "My-Agent", "Agent"))
    assert collector.internals_for(SESSION) != {}

    collector.discard(SESSION)
    assert collector.internals_for(SESSION) == {}


async def test_recording_is_synchronous():
    """It runs inline on the publishing coroutine, so no queue can drop an event."""
    collector = NodeInternalsCollector()
    collector.record(_node_creation(AGENT, "My-Agent", "Agent"))
    collector.record(_node_destruction(AGENT, 1.0))

    assert collector.internals_for(SESSION)[AGENT]["latency"] == {"total_time": 1.0}


@pytest.mark.parametrize(
    "action, expected",
    [("allow", "allow"), ("transform", "transform"), ("block", "block")],
)
async def test_decision_actions_serialize_to_their_legacy_strings(action, expected):
    decision = GuardrailDecision(action=action, reason="r")
    collector = _collect(
        _node_creation(AGENT, "My-Agent", "Agent"),
        _event(
            "middleware.creation", middleware_type_id=GUARD_MW, middleware_name="rail"
        ),
        _llm_response(AGENT),
        _event(
            "middleware.guard.input.response",
            spatial_parent_llm_invoke_id=LLM_CALL,
            parent_middleware_type_id=GUARD_MW,
            decision=decision,
        ),
    )

    trace = collector.internals_for(SESSION)["node-agent"]["guard_details"][0]
    assert trace["action"] == expected
