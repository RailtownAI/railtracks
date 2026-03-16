import json
from collections import defaultdict

import pytest
from uuid import UUID

from railtracks.evaluations.point import (
    EdgeDataPoint,
    MessageRole,
    Status,
    construct_graph,
    extract_agent_data_points,
    extract_agent_io,
    extract_llm_details,
    extract_tool_details,
    load_session,
    resolve_file_paths,
)

from .conftest import AGENT_ID, TOOL1_ID, TOOL2_ID, SESSION_ID


# ── load_session ──────────────────────────────────────────────────────────────


def test_load_session_valid(tmp_path, session_json):
    path = tmp_path / "session.json"
    path.write_text(json.dumps(session_json))
    data = load_session(path)
    assert data["session_id"] == str(SESSION_ID)


def test_load_session_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_session(tmp_path / "missing.json")


def test_load_session_invalid_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("not valid json{{{")
    with pytest.raises(ValueError):
        load_session(path)


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


# ── resolve_file_paths ───────────────────────────────────────────────────────


def test_resolve_file_paths_single_file(tmp_path, session_json):
    path = tmp_path / "session.json"
    path.write_text(json.dumps(session_json))
    result = resolve_file_paths(str(path))
    assert result == [str(path)]


def test_resolve_file_paths_list(tmp_path, session_json):
    path = tmp_path / "session.json"
    path.write_text(json.dumps(session_json))
    result = resolve_file_paths([str(path)])
    assert result == [str(path)]


def test_resolve_file_paths_directory(tmp_path, session_json):
    (tmp_path / "s1.json").write_text(json.dumps(session_json))
    (tmp_path / "s2.json").write_text(json.dumps(session_json))
    result = resolve_file_paths(str(tmp_path))
    assert len(result) == 2


def test_resolve_file_paths_missing_file():
    with pytest.raises(FileNotFoundError):
        resolve_file_paths("/nonexistent/path/session.json")


def test_resolve_file_paths_invalid_type():
    with pytest.raises(TypeError):
        resolve_file_paths(12345)  # type: ignore


def test_resolve_file_paths_directory_in_list(tmp_path):
    with pytest.raises(ValueError):
        resolve_file_paths([str(tmp_path)])


# ── extract_agent_data_points ─────────────────────────────────────────────────


def test_extract_agent_data_points_from_file(tmp_path, session_json):
    path = tmp_path / "session.json"
    path.write_text(json.dumps(session_json))
    data_points = extract_agent_data_points(str(path))
    assert len(data_points) == 1
    dp = data_points[0]
    assert dp.agent_name == "TestAgent"
    assert dp.session_id == SESSION_ID
    assert len(dp.llm_details.calls) == 1


def test_extract_agent_data_points_tool_details(tmp_path, session_json):
    path = tmp_path / "session.json"
    path.write_text(json.dumps(session_json))
    data_points = extract_agent_data_points(str(path))
    dp = data_points[0]
    assert "get_stock_price" in dp.tool_details.tool_names
    assert len(dp.tool_details.calls) == 1
    assert dp.tool_details.calls[0].output == 214.88
