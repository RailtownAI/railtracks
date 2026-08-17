"""Backward compatibility of the session document's `details.internals`."""

import pytest
import railtracks as rt
from jsonschema import validate

# The exact key set the legacy `RequestDetails` encoder emitted, in its order.
LEGACY_LLM_DETAIL_KEYS = [
    "model_name",
    "model_provider",
    "input",
    "output",
    "input_tokens",
    "output_tokens",
    "total_cost",
    "system_fingerprint",
    "latency",
]


@pytest.fixture
def tool_calling_payload(mock_llm):
    """A run of an agent that calls one tool, then answers."""

    @rt.function_node
    def secret_phrase() -> str:
        """Returns the secret phrase."""
        return "open sesame"

    model = mock_llm(
        requested_tool_calls=[
            rt.llm.ToolCall(
                name="secret_phrase", identifier="id_42424242", arguments={}
            )
        ]
    )
    agent = rt.agent_node(
        name="Compat-Agent",
        tool_nodes=[secret_phrase],
        llm=model,
        system_message="You are a helpful assistant.",
    )

    async def run():
        with rt.Session(flow_name="legacy-trace-compat") as session:
            await rt.call(agent, "What is the secret phrase?")
        return session.payload()

    return run


def _nodes(payload):
    return {n["name"]: n for n in payload["runs"][0]["nodes"]}


async def test_payload_matches_the_state_schema(
    tool_calling_payload, json_state_schema
):
    validate(await tool_calling_payload(), json_state_schema)


async def test_every_node_reports_an_internals_object(tool_calling_payload):
    """Never null: consumers rely on a `.get("internals", {})` default, and a null
    defeats it because the key is present."""
    payload = await tool_calling_payload()

    for node in payload["runs"][0]["nodes"]:
        snapshot = node
        while snapshot is not None:
            assert isinstance(snapshot["details"]["internals"], dict)
            snapshot = snapshot.get("parent")


async def test_agent_node_carries_the_legacy_three_key_block(tool_calling_payload):
    payload = await tool_calling_payload()
    internals = _nodes(payload)["Compat-Agent"]["details"]["internals"]

    assert list(internals) == ["guard_details", "llm_details", "latency"]
    assert internals["guard_details"] == []
    assert internals["latency"]["total_time"] > 0


async def test_llm_details_entries_keep_the_legacy_key_set(tool_calling_payload):
    payload = await tool_calling_payload()
    calls = _nodes(payload)["Compat-Agent"]["details"]["internals"]["llm_details"]

    assert calls, "a tool-calling agent makes at least one LLM call"
    for call in calls:
        assert list(call) == LEGACY_LLM_DETAIL_KEYS


async def test_llm_details_carry_the_values_the_visualizer_renders(
    tool_calling_payload,
):
    """Model, provider, tokens, cost and latency all come off the response event."""
    payload = await tool_calling_payload()
    call = _nodes(payload)["Compat-Agent"]["details"]["internals"]["llm_details"][-1]

    assert call["model_name"] == "MockLLM"
    assert call["model_provider"] is not None
    assert call["input_tokens"] == 42
    assert call["output_tokens"] == 42
    assert call["total_cost"] == pytest.approx(0.00042)
    assert call["latency"] == pytest.approx(1.42)
    assert call["system_fingerprint"] == "fp_4242424242"


async def test_llm_details_are_in_call_order_with_a_growing_history(
    tool_calling_payload,
):
    """The visualizer takes llm_details[-1] as the node's headline model, so order
    matters; the tool loop appends to the history each turn."""
    payload = await tool_calling_payload()
    calls = _nodes(payload)["Compat-Agent"]["details"]["internals"]["llm_details"]

    lengths = [len(call["input"]) for call in calls]
    assert lengths == sorted(lengths)
    assert lengths[-1] > lengths[0], "the tool result should extend the history"


async def test_messages_keep_the_role_content_encoding(tool_calling_payload):
    payload = await tool_calling_payload()
    call = _nodes(payload)["Compat-Agent"]["details"]["internals"]["llm_details"][0]

    for message in call["input"]:
        assert set(message) == {"role", "content"}
    assert set(call["output"]) == {"role", "content"}
    assert call["output"]["role"] == "assistant"


async def test_tool_call_content_survives_as_a_list_of_calls(tool_calling_payload):
    """An assistant turn that calls tools encodes content as ToolCall objects, which
    is what the visualizer branches on to label the turn."""
    payload = await tool_calling_payload()
    calls = _nodes(payload)["Compat-Agent"]["details"]["internals"]["llm_details"]

    tool_call_outputs = [
        c["output"] for c in calls if isinstance(c["output"]["content"], list)
    ]
    assert tool_call_outputs, "the mock model requests a tool call"
    for tool_call in tool_call_outputs[0]["content"]:
        assert set(tool_call) == {"identifier", "name", "arguments"}


async def test_tool_node_reports_latency_and_nothing_else(tool_calling_payload):
    """A function node never had the LLM keys at all — not even empty ones."""
    payload = await tool_calling_payload()
    internals = _nodes(payload)["secret_phrase"]["details"]["internals"]

    assert list(internals) == ["latency"]
    assert internals["latency"]["total_time"] > 0


async def test_tool_inputs_and_outputs_stay_on_the_edge(tool_calling_payload):
    """Tool I/O is read off the inbound edge, not the node — the node carries none."""
    payload = await tool_calling_payload()
    run = payload["runs"][0]
    tool_id = _nodes(payload)["secret_phrase"]["identifier"]

    inbound = [e for e in run["edges"] if e["target"] == tool_id]
    assert len(inbound) == 1
    details = inbound[0]["details"]
    assert set(details) >= {"input_args", "input_kwargs", "status", "output"}
    assert details["status"] == "Completed"
    assert details["output"] == "open sesame"


async def test_parent_snapshots_omit_latency(tool_calling_payload):
    """A temporal parent predates the completion that `latency` measures, so it never
    carried one on `main` either."""
    payload = await tool_calling_payload()

    seen_a_parent = False
    for node in payload["runs"][0]["nodes"]:
        parent = node.get("parent")
        while parent is not None:
            seen_a_parent = True
            assert "latency" not in parent["details"]["internals"]
            parent = parent.get("parent")
    assert seen_a_parent, "the fixture should produce at least one updated node"


async def test_node_ids_line_up_with_the_collected_blocks(tool_calling_payload):
    """The rebuild keys on the node uuid the graph serializer uses; a mismatch would
    silently leave every block empty."""
    payload = await tool_calling_payload()
    nodes = payload["runs"][0]["nodes"]

    assert nodes, "the run has nodes"
    assert all(node["details"]["internals"] for node in nodes), (
        "every node in this fixture ran, so every block should be populated"
    )
