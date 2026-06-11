import json
from collections import defaultdict

import pytest
from uuid import UUID

from railtracks.evaluations.point import (
    EdgeDataPoint,
    MessageRole,
    Status,
    construct_graph,
    data_points_from_payload,
    extract_agent_data_points,
    extract_agent_io,
    extract_llm_details,
    extract_tool_details,
)

from .conftest import AGENT_ID, TOOL1_ID, TOOL2_ID, SESSION_ID


# ── construct_graph ───────────────────────────────────────────────────────────


def test_construct_graph_builds_adjacency(edges):
    graph, _ = construct_graph(edges)
    assert TOOL1_ID in graph[AGENT_ID]
    assert TOOL2_ID in graph[AGENT_ID]
    assert AGENT_ID in graph[None]


def test_construct_graph_sink_list(edges):
    _, sink_list = construct_graph(edges)
    assert len(sink_list[AGENT_ID]) == 1
    assert sink_list[AGENT_ID][0].source is None


def test_construct_graph_empty():
    graph, sink_list = construct_graph({})
    assert len(graph) == 0
    assert len(sink_list) == 0


# ── extract_llm_details ───────────────────────────────────────────────────────


def test_extract_llm_details_single_call():
    raw = [
        {
            "model_name": "gpt-4",
            "model_provider": "OpenAI",
            "input": [{"role": "user", "content": "Hello"}],
            "output": {"role": "assistant", "content": "Hi"},
            "input_tokens": 10,
            "output_tokens": 5,
            "total_cost": 0.001,
            "latency": 1.0,
        }
    ]
    result = extract_llm_details(raw)
    assert len(result.calls) == 1
    call = result.calls[0]
    assert call.model_name == "gpt-4"
    assert call.model_provider == "OpenAI"
    assert call.input_tokens == 10
    assert call.output_tokens == 5
    assert call.index == 0
    assert call.output.role == MessageRole.ASSISTANT


def test_extract_llm_details_preserves_index():
    raw = [
        {
            "model_name": "gpt-4",
            "model_provider": "OpenAI",
            "input": [],
            "output": {"role": "assistant", "content": "A"},
            "input_tokens": 1,
            "output_tokens": 1,
            "total_cost": 0.0,
            "latency": 1.0,
        },
        {
            "model_name": "gpt-4",
            "model_provider": "OpenAI",
            "input": [],
            "output": {"role": "assistant", "content": "B"},
            "input_tokens": 1,
            "output_tokens": 1,
            "total_cost": 0.0,
            "latency": 1.0,
        },
    ]
    result = extract_llm_details(raw)
    assert result.calls[0].index == 0
    assert result.calls[1].index == 1


def test_extract_llm_details_empty():
    result = extract_llm_details([])
    assert result.calls == []


# ── extract_tool_details ──────────────────────────────────────────────────────


def test_extract_tool_details(agent_node, tool_nodes, edges):
    nodes = {AGENT_ID: agent_node, **tool_nodes}
    graph, _ = construct_graph(edges)
    details = extract_tool_details(nodes, edges, graph, AGENT_ID)
    assert "tool_one" in details.tool_names
    assert "tool_two" in details.tool_names
    assert len(details.calls) == 2


def test_extract_tool_details_no_tools(agent_node):
    uuid_list: list[UUID] = []
    nodes = {AGENT_ID: agent_node}
    graph = {AGENT_ID: uuid_list}
    details = extract_tool_details(nodes, {}, graph, AGENT_ID)
    assert details.tool_names == set()
    assert details.calls == []


def test_extract_tool_details_call_fields(agent_node, tool_nodes, edges):
    nodes = {AGENT_ID: agent_node, **tool_nodes}
    graph, _ = construct_graph(edges)
    details = extract_tool_details(nodes, edges, graph, AGENT_ID)
    call_by_name = {c.name: c for c in details.calls}
    assert call_by_name["tool_one"].output == 214.88
    assert call_by_name["tool_one"].status == Status.COMPLETED
    assert call_by_name["tool_one"].arguments.kwargs == {"ticker": "AMZN"}


# ── extract_agent_io ──────────────────────────────────────────────────────────


def test_extract_agent_io_completed_edge(agent_node, edges):
    _, sink_list = construct_graph(edges)
    agent_input, agent_output = extract_agent_io(sink_list, agent_node, "test.json")
    assert agent_input["args"] == ["What is the stock price?"]
    assert agent_output == {"answer": "Here is the stock info"}


def test_extract_agent_io_no_edges(agent_node):
    agent_input, agent_output = extract_agent_io(defaultdict(list), agent_node, "test.json")
    assert agent_input == {}
    assert agent_output == {}


def test_extract_agent_io_ignores_failed_edge(agent_node):
    failed_sink = {
        AGENT_ID: [
            EdgeDataPoint(
                identifier=UUID("eeeeeeee-0000-0000-0000-000000000001"),
                source=None,
                target=AGENT_ID,
                details={"input_args": [], "input_kwargs": {}, "status": "Failed", "output": None},
            )
        ]
    }
    agent_input, agent_output = extract_agent_io(failed_sink, agent_node, "test.json")
    assert agent_input == {}
    assert agent_output == {}


# ── data_points_from_payload ─────────────────────────────────────────────────


def test_data_points_from_payload(session_json):
    data_points = data_points_from_payload(session_json)
    assert len(data_points) == 1
    dp = data_points[0]
    assert dp.agent_name == "TestAgent"
    assert dp.session_id == SESSION_ID
    assert len(dp.llm_details.calls) == 1


def test_data_points_from_payload_tool_details(session_json):
    dp = data_points_from_payload(session_json)[0]
    assert "get_stock_price" in dp.tool_details.tool_names
    assert len(dp.tool_details.calls) == 1
    assert dp.tool_details.calls[0].output == 214.88


# ── extract_agent_data_points (workspace DB) ─────────────────────────────────


@pytest.fixture
def seeded_workspace(tmp_path, monkeypatch):
    """A workspace DB seeded with one agent session (agent + tool + llm call)."""
    from types import SimpleNamespace

    from railtracks.llm import AssistantMessage, MessageHistory, UserMessage
    from railtracks.persistence.repository import SessionRepository
    from railtracks.utils.profiling import Stamp

    monkeypatch.setenv("RAILTRACKS_HOME", str(tmp_path))
    home = tmp_path / ".railtracks"
    home.mkdir(parents=True, exist_ok=True)

    repo = SessionRepository(home)
    repo.start_session(
        session_id=str(SESSION_ID),
        flow_id="f-1",
        flow_name="Stock Analysis",
        session_name=None,
        start_time=100.0,
    )
    repo.start_run(run_id="run-1", session_id=str(SESSION_ID), name="TestAgent", start_time=100.0)
    repo.upsert_node(node_uuid=str(AGENT_ID), run_id="run-1", name="TestAgent", node_type="Agent")
    repo.upsert_node(node_uuid=str(TOOL1_ID), run_id="run-1", name="get_stock_price", node_type="Tool")
    repo.record_request_creation(
        request_id="dddddddd-0000-0000-0000-000000000003",
        run_id="run-1",
        source_node_uuid=None,
        sink_node_uuid=str(AGENT_ID),
        input_args=["What is the stock price?"],
        input_kwargs={},
        stamp=Stamp(time=100.0, step=0, identifier="created"),
    )
    repo.record_request_creation(
        request_id="dddddddd-0000-0000-0000-000000000001",
        run_id="run-1",
        source_node_uuid=str(AGENT_ID),
        sink_node_uuid=str(TOOL1_ID),
        input_args=[],
        input_kwargs={"ticker": "AMZN"},
        stamp=Stamp(time=101.0, step=1, identifier="tool created"),
    )
    repo.record_request_success(
        "dddddddd-0000-0000-0000-000000000001",
        output=214.88,
        stamp=Stamp(time=102.0, step=2, identifier="tool done"),
    )
    repo.record_request_success(
        "dddddddd-0000-0000-0000-000000000003",
        output={"answer": "The stock is $100."},
        stamp=Stamp(time=103.0, step=3, identifier="agent done"),
    )
    details = SimpleNamespace(
        input=MessageHistory([UserMessage("What is the stock price?")]),
        output=AssistantMessage("The stock is $100."),
        model_name="gpt-4",
        model_provider="OpenAI",
        input_tokens=50,
        output_tokens=10,
        total_cost=0.001,
        system_fingerprint=None,
        latency=1.2,
    )
    repo.record_llm_call(details, node_uuid=str(AGENT_ID), session_id=str(SESSION_ID), call_index=0)
    repo.end_run("run-1", end_time=103.0, status="Completed")
    repo.end_session(str(SESSION_ID), end_time=103.0, status="Completed")
    return home


def test_extract_agent_data_points_from_db(seeded_workspace):
    data_points = extract_agent_data_points(str(SESSION_ID), railtracks_home=seeded_workspace)
    assert len(data_points) == 1
    dp = data_points[0]
    assert dp.agent_name == "TestAgent"
    assert dp.session_id == SESSION_ID
    assert len(dp.llm_details.calls) == 1
    call = dp.llm_details.calls[0]
    assert call.model_name == "gpt-4"
    assert call.input_tokens == 50
    assert call.output.role == MessageRole.ASSISTANT
    assert dp.agent_input == {"args": ["What is the stock price?"], "kwargs": {}}
    assert dp.agent_output == {"answer": "The stock is $100."}


def test_extract_agent_data_points_tool_details_from_db(seeded_workspace):
    dp = extract_agent_data_points(str(SESSION_ID), railtracks_home=seeded_workspace)[0]
    assert "get_stock_price" in dp.tool_details.tool_names
    assert len(dp.tool_details.calls) == 1
    tool_call = dp.tool_details.calls[0]
    assert tool_call.output == 214.88
    assert tool_call.arguments.kwargs == {"ticker": "AMZN"}
    assert tool_call.status == Status.COMPLETED


def test_extract_agent_data_points_all_sessions(seeded_workspace):
    # None means every session in the workspace
    data_points = extract_agent_data_points(railtracks_home=seeded_workspace)
    assert len(data_points) == 1


def test_extract_agent_data_points_unknown_session(seeded_workspace):
    assert extract_agent_data_points("not-a-session", railtracks_home=seeded_workspace) == []
