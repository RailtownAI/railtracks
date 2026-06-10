"""Tests for the SQLite-backed /api/v2/* viz_server endpoints."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from railtracks.cli import viz_server
from railtracks.llm import AssistantMessage, MessageHistory, ToolCall, UserMessage
from railtracks.persistence.repository import SessionRepository
from railtracks.utils.profiling import Stamp


def _stamp(step: int, time: float = 0.0, identifier: str = "s") -> Stamp:
    return Stamp(time=time, step=step, identifier=identifier)


@pytest.fixture
def tmp_railtracks_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RAILTRACKS_HOME", str(tmp_path))
    home = tmp_path / ".railtracks"
    home.mkdir(parents=True, exist_ok=True)
    return home


@pytest.fixture
def seeded_repo(tmp_railtracks_home: Path) -> SessionRepository:
    repo = SessionRepository(tmp_railtracks_home)
    repo.start_session(
        session_id="s-1",
        flow_id="f-1",
        flow_name="demo-flow",
        session_name=None,
        start_time=100.0,
    )
    repo.start_run(run_id="r-1", session_id="s-1", name="Agent", start_time=100.0)
    repo.upsert_node(node_uuid="n-1", run_id="r-1", name="Agent", node_type="Agent")
    repo.record_node_version("n-1", _stamp(0, 100.0, "created"))
    repo.record_node_version("n-1", _stamp(3, 103.0, "done"))
    repo.record_request_creation(
        request_id="req-1",
        run_id="r-1",
        source_node_uuid=None,
        sink_node_uuid="n-1",
        input_args=("hello",),
        input_kwargs={},
        stamp=_stamp(0, 100.0),
    )
    repo.record_stamp("s-1", _stamp(0, 100.0, "created"))
    repo.record_stamp("s-1", _stamp(3, 103.0, "done"))
    repo.record_request_success(
        "req-1", output={"answer": 42}, stamp=_stamp(3, 103.0)
    )
    repo.end_run("r-1", end_time=103.0, status="Completed")

    calls = [ToolCall(identifier="t-1", name="search", arguments={"q": "x"})]
    details = SimpleNamespace(
        input=MessageHistory([UserMessage("find x")]),
        output=AssistantMessage(calls),
        model_name="gpt-4o",
        model_provider="openai",
        input_tokens=100,
        output_tokens=20,
        total_cost=0.002,
        system_fingerprint=None,
        latency=0.7,
    )
    repo.record_llm_call(details, node_uuid="n-1", session_id="s-1", call_index=0)
    repo.end_session("s-1", end_time=103.0, status="Completed")
    return repo


@pytest.fixture
def client(seeded_repo: SessionRepository, monkeypatch) -> TestClient:
    # point the server at the seeded test engine instead of its cached one
    monkeypatch.setattr(viz_server, "_engine", seeded_repo._engine)
    return TestClient(viz_server.app)


def test_v2_sessions_list_with_aggregates(client: TestClient) -> None:
    resp = client.get("/api/v2/sessions")
    assert resp.status_code == 200
    sessions = resp.json()
    assert len(sessions) == 1
    s = sessions[0]
    assert s["session_id"] == "s-1"
    assert s["flow_name"] == "demo-flow"
    assert s["run_count"] == 1
    assert s["llm_call_count"] == 1
    assert s["total_input_tokens"] == 100
    assert s["total_cost"] == 0.002


def test_v2_session_runs(client: TestClient) -> None:
    resp = client.get("/api/v2/sessions/s-1/runs")
    assert resp.status_code == 200
    runs = resp.json()
    assert len(runs) == 1
    assert runs[0]["run_id"] == "r-1"
    assert runs[0]["status"] == "Completed"


def test_v2_run_nodes(client: TestClient) -> None:
    resp = client.get("/api/v2/runs/r-1/nodes")
    assert resp.status_code == 200
    nodes = resp.json()
    assert [n["node_uuid"] for n in nodes] == ["n-1"]


def test_v2_run_edges_with_joined_names(client: TestClient) -> None:
    resp = client.get("/api/v2/runs/r-1/edges")
    assert resp.status_code == 200
    edges = resp.json()
    assert len(edges) == 1
    edge = edges[0]
    assert edge["request_id"] == "req-1"
    assert edge["sink_node_name"] == "Agent"
    assert edge["sink_node_type"] == "Agent"
    assert edge["output_json"] == {"answer": 42}


def test_v2_llm_calls_flat_list(client: TestClient) -> None:
    resp = client.get("/api/v2/llm-calls")
    assert resp.status_code == 200
    calls = resp.json()
    assert len(calls) == 1
    call = calls[0]
    assert call["model_name"] == "gpt-4o"
    assert call["node_name"] == "Agent"
    assert call["flow_name"] == "demo-flow"

    # filters
    assert client.get("/api/v2/llm-calls?model=gpt-4o").json() != []
    assert client.get("/api/v2/llm-calls?model=other").json() == []
    assert client.get("/api/v2/llm-calls?session_id=s-1").json() != []
    assert client.get("/api/v2/llm-calls?session_id=nope").json() == []


def test_v2_session_llm_calls(client: TestClient) -> None:
    resp = client.get("/api/v2/sessions/s-1/llm-calls")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_v2_tool_calls(client: TestClient) -> None:
    resp = client.get("/api/v2/tool-calls")
    assert resp.status_code == 200
    calls = resp.json()
    assert len(calls) == 1
    assert calls[0]["name"] == "search"
    assert calls[0]["arguments_json"] == {"q": "x"}

    assert client.get("/api/v2/tool-calls?name=search").json() != []
    assert client.get("/api/v2/tool-calls?name=other").json() == []
    assert client.get("/api/v2/tool-calls?run_id=r-1").json() != []
    assert client.get("/api/v2/tool-calls?run_id=nope").json() == []


def test_v2_session_full_legacy_shape(client: TestClient) -> None:
    resp = client.get("/api/v2/sessions/s-1/full")
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["session_id"] == "s-1"
    assert payload["flow_name"] == "demo-flow"
    assert len(payload["runs"]) == 1

    run = payload["runs"][0]
    assert run["run_id"] == "r-1"
    assert run["status"] == "Completed"

    # vertex shape with temporal parent chain
    assert len(run["nodes"]) == 1
    vertex = run["nodes"][0]
    assert vertex["identifier"] == "n-1"
    assert vertex["stamp"]["step"] == 3
    assert vertex["parent"]["stamp"]["step"] == 0
    llm_details = vertex["details"]["internals"]["llm_details"]
    assert len(llm_details) == 1
    assert llm_details[0]["input_tokens"] == 100
    assert llm_details[0]["input"][0] == {"role": "user", "content": "find x"}
    assert llm_details[0]["output"]["role"] == "assistant"

    # edge shape with status/output details and creation parent
    assert len(run["edges"]) == 1
    edge = run["edges"][0]
    assert edge["target"] == "n-1"
    assert edge["details"]["status"] == "Completed"
    assert edge["details"]["output"] == {"answer": 42}
    assert edge["parent"]["details"]["status"] == "Open"

    # steps reconstructed from the stamps table
    assert [s["step"] for s in run["steps"]] == [0, 3]


def test_v2_session_full_unknown_session_404(client: TestClient) -> None:
    assert client.get("/api/v2/sessions/missing/full").status_code == 404
