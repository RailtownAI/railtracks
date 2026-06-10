"""Dual-write checkpoint (Step 5 of the SQLite migration).

While both persistence paths are live, every session must produce a
JSON file AND a semantically matching SQLite row set. These tests run
real flows (function nodes, MockLLM agents, a failure path) and compare
the two outputs. They are deleted in Step 7 when the JSON path is cut.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import railtracks as rt
from sqlmodel import Session as DBSession
from sqlmodel import select

from railtracks.persistence.connection import get_engine
from railtracks.persistence.models import (
    FailureRow,
    LLMCallRow,
    MessageRow,
    NodeRow,
    RequestRow,
    RunRow,
    SessionRow,
)


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    # the autouse RAILTRACKS_TEST_MODE fixture disables save_state by
    # default; these tests exist precisely to verify persistence.
    monkeypatch.setenv("RAILTRACKS_ALLOW_PERSISTENCE", "1")
    monkeypatch.setenv("RAILTRACKS_HOME", str(tmp_path))
    return tmp_path / ".railtracks"


def _json_payload(home: Path, session_id: str) -> dict:
    matches = list((home / "data" / "sessions").glob(f"*{session_id}.json"))
    assert len(matches) == 1, f"expected exactly one JSON file, got {matches}"
    return json.loads(matches[0].read_text())


def _db_rows(home: Path, model, *where):
    engine = get_engine(home)
    try:
        with DBSession(engine) as s:
            stmt = select(model)
            for clause in where:
                stmt = stmt.where(clause)
            return s.exec(stmt).all()
    finally:
        engine.dispose()


@rt.function_node
def greet() -> str:
    return "hello world"


@rt.function_node
def shout(text: str) -> str:
    return text.upper()


@rt.function_node
def explode() -> str:
    raise ValueError("intentional kaboom")


async def test_function_flow_dual_write(isolated_home) -> None:
    with rt.Session(flow_name="dualwrite") as sess:
        await rt.call(greet)
        await rt.call(shout, "hi")

    payload = _json_payload(isolated_home, sess._identifier)

    sessions = _db_rows(isolated_home, SessionRow)
    assert len(sessions) == 1
    srow = sessions[0]
    assert srow.session_id == sess._identifier == payload["session_id"]
    assert srow.flow_name == payload["flow_name"] == "dualwrite"
    assert srow.status == "Completed"
    assert srow.end_time is not None

    # one run per insertion request, ids must match the JSON run ids
    runs = _db_rows(isolated_home, RunRow)
    json_runs = payload["runs"]
    assert {r.run_id for r in runs} == {r["run_id"] for r in json_runs}
    assert all(r.status == "Completed" for r in runs)

    # every JSON vertex has a node row; every edge a request row
    json_nodes = {n["identifier"] for run in json_runs for n in run["nodes"]}
    json_edges = {e["identifier"] for run in json_runs for e in run["edges"]}
    assert {n.node_uuid for n in _db_rows(isolated_home, NodeRow)} == json_nodes
    db_requests = _db_rows(isolated_home, RequestRow)
    assert {r.request_id for r in db_requests} == json_edges
    assert all(r.status == "Completed" for r in db_requests)
    # outputs round-tripped through the same encoder shape
    outputs = {r.output_json for r in db_requests}
    assert "hello world" in outputs
    assert "HI" in outputs


async def test_llm_agent_dual_write(isolated_home, mock_llm) -> None:
    agent = rt.agent_node(
        name="Echo",
        system_message="echo things",
        llm=mock_llm(custom_response="echoed!"),
    )
    with rt.Session(flow_name="llmflow") as sess:
        await rt.call(agent, user_input="say something")

    payload = _json_payload(isolated_home, sess._identifier)

    calls = _db_rows(isolated_home, LLMCallRow)
    assert len(calls) == 1
    call = calls[0]
    assert call.session_id == sess._identifier
    assert call.model_name == "MockLLM"
    assert call.input_tokens == 42
    assert call.total_cost == 0.00042

    messages = _db_rows(isolated_home, MessageRow)
    directions = {(m.direction, m.role) for m in messages}
    assert ("output", "assistant") in directions
    assert ("input", "user") in directions

    # JSON side carries the same call nested in node details
    json_llm_details = [
        d
        for run in payload["runs"]
        for n in run["nodes"]
        for d in (n["details"]["internals"].get("llm_details") or [])
    ]
    assert len(json_llm_details) == 1
    assert json_llm_details[0]["input_tokens"] == call.input_tokens
    assert json_llm_details[0]["total_cost"] == call.total_cost


async def test_failure_flow_dual_write(isolated_home) -> None:
    with pytest.raises(Exception):
        with rt.Session(flow_name="failflow", end_on_error=True) as sess:
            await rt.call(explode)

    failures = _db_rows(isolated_home, FailureRow)
    assert len(failures) >= 1
    failure = failures[0]
    assert failure.exception_type == "ValueError"
    assert "intentional kaboom" in failure.message
    assert "Traceback" in failure.traceback

    failed_requests = _db_rows(
        isolated_home, RequestRow, RequestRow.output_kind == "failure"
    )
    assert len(failed_requests) >= 1

    # JSON side recorded the same failure shape (commit 6b44cf8a format)
    payload = _json_payload(isolated_home, sess._identifier)
    json_outputs = [
        e["details"]["output"]
        for run in payload["runs"]
        for e in run["edges"]
        if isinstance(e["details"].get("output"), dict)
        and "traceback" in e["details"]["output"]
    ]
    assert any(o["type"] == "ValueError" for o in json_outputs)


async def test_v2_full_endpoint_matches_json_file(isolated_home, mock_llm, monkeypatch) -> None:
    """The /api/v2/sessions/{id}/full bridge endpoint must agree with the
    JSON file on everything the visualizer reads."""
    from fastapi.testclient import TestClient

    from railtracks.cli import viz_server
    from railtracks.persistence.connection import get_engine

    agent = rt.agent_node(
        name="Echo",
        system_message="echo things",
        llm=mock_llm(custom_response="echoed!"),
    )
    with rt.Session(flow_name="fullcheck") as sess:
        await rt.call(agent, user_input="say something")
        await rt.call(shout, "hi")

    json_payload = _json_payload(isolated_home, sess._identifier)

    monkeypatch.setattr(viz_server, "_engine", get_engine(isolated_home))
    client = TestClient(viz_server.app)
    resp = client.get(f"/api/v2/sessions/{sess._identifier}/full")
    assert resp.status_code == 200
    sql_payload = resp.json()

    # session header
    for key in ("flow_name", "flow_id", "session_id", "session_name", "start_time"):
        assert sql_payload[key] == json_payload[key], key

    # same runs, same wiring
    json_runs = {r["run_id"]: r for r in json_payload["runs"]}
    sql_runs = {r["run_id"]: r for r in sql_payload["runs"]}
    assert sql_runs.keys() == json_runs.keys()

    for run_id, json_run in json_runs.items():
        sql_run = sql_runs[run_id]
        assert sql_run["status"] == json_run["status"]
        assert {n["identifier"] for n in sql_run["nodes"]} == {
            n["identifier"] for n in json_run["nodes"]
        }
        assert {e["identifier"] for e in sql_run["edges"]} == {
            e["identifier"] for e in json_run["edges"]
        }
        # edge statuses and outputs agree
        json_edges = {e["identifier"]: e for e in json_run["edges"]}
        for sql_edge in sql_run["edges"]:
            json_edge = json_edges[sql_edge["identifier"]]
            assert sql_edge["source"] == json_edge["source"]
            assert sql_edge["target"] == json_edge["target"]
            assert sql_edge["details"]["status"] == json_edge["details"]["status"]
            assert sql_edge["details"]["output"] == json_edge["details"]["output"]
        # llm token/cost numbers agree per node
        json_llm = {
            n["identifier"]: n["details"]["internals"].get("llm_details") or []
            for n in json_run["nodes"]
        }
        for sql_node in sql_run["nodes"]:
            sql_details = sql_node["details"]["internals"].get("llm_details") or []
            expected = json_llm[sql_node["identifier"]]
            assert len(sql_details) == len(expected)
            for got, want in zip(sql_details, expected):
                for key in ("model_name", "input_tokens", "output_tokens", "total_cost"):
                    assert got[key] == want[key], key


async def test_save_state_false_writes_nothing(isolated_home) -> None:
    with rt.Session(flow_name="nostate", save_state=False) as sess:
        await rt.call(greet)

    sessions_dir = isolated_home / "data" / "sessions"
    assert not list(sessions_dir.glob("*.json")) if sessions_dir.exists() else True
    db_path = isolated_home / "data" / "railtracks.db"
    if db_path.exists():
        assert (
            _db_rows(isolated_home, SessionRow, SessionRow.session_id == sess._identifier)
            == []
        )
