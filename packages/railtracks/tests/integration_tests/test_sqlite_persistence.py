"""End-to-end SQLite persistence tests (post-cut, Step 7).

Real flows — function nodes, MockLLM agents, failure paths — asserting
directly on the workspace DB. The legacy-shape bridge is covered via
the /api/v2/sessions/{id}/full endpoint.
"""

from __future__ import annotations

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


def _db_rows(home, model, *where):
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


async def test_function_flow_persists(isolated_home) -> None:
    with rt.Session(flow_name="sqliteflow") as sess:
        await rt.call(greet)
        await rt.call(shout, "hi")

    # no JSON files anymore — the DB is the only artifact
    sessions_dir = isolated_home / "data" / "sessions"
    assert not sessions_dir.exists() or list(sessions_dir.glob("*.json")) == []

    sessions = _db_rows(isolated_home, SessionRow)
    assert len(sessions) == 1
    srow = sessions[0]
    assert srow.session_id == sess._identifier
    assert srow.flow_name == "sqliteflow"
    assert srow.status == "Completed"
    assert srow.end_time is not None

    runs = _db_rows(isolated_home, RunRow)
    assert len(runs) == 2
    assert all(r.status == "Completed" for r in runs)

    requests = _db_rows(isolated_home, RequestRow)
    outputs = {r.output_json for r in requests}
    assert "hello world" in outputs
    assert "HI" in outputs

    nodes = _db_rows(isolated_home, NodeRow)
    assert {n.name for n in nodes} == {"greet", "shout"}


async def test_llm_agent_persists(isolated_home, mock_llm) -> None:
    agent = rt.agent_node(
        name="Echo",
        system_message="echo things",
        llm=mock_llm(custom_response="echoed!"),
    )
    with rt.Session(flow_name="llmflow") as sess:
        await rt.call(agent, user_input="say something")

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


async def test_failure_flow_persists(isolated_home) -> None:
    with pytest.raises(Exception):
        with rt.Session(flow_name="failflow", end_on_error=True):
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


async def test_full_endpoint_serves_legacy_shape(isolated_home, mock_llm, monkeypatch) -> None:
    """The bridge endpoint serves the visualizer-consumable nested shape."""
    from fastapi.testclient import TestClient

    from railtracks.cli import viz_server

    agent = rt.agent_node(
        name="Echo",
        system_message="echo things",
        llm=mock_llm(custom_response="echoed!"),
    )
    with rt.Session(flow_name="fullcheck") as sess:
        await rt.call(agent, user_input="say something")
        await rt.call(shout, "hi")

    monkeypatch.setattr(viz_server, "_engine", get_engine(isolated_home))
    client = TestClient(viz_server.app)

    # both the legacy path and the v2 path serve the same payload
    legacy = client.get(f"/api/sessions/{sess._identifier}")
    v2 = client.get(f"/api/v2/sessions/{sess._identifier}/full")
    assert legacy.status_code == v2.status_code == 200
    assert legacy.json() == v2.json()

    payload = v2.json()
    assert payload["flow_name"] == "fullcheck"
    assert len(payload["runs"]) == 2
    llm_details = [
        d
        for run in payload["runs"]
        for n in run["nodes"]
        for d in (n["details"]["internals"].get("llm_details") or [])
    ]
    assert len(llm_details) == 1
    assert llm_details[0]["input_tokens"] == 42

    # list endpoint serves every session
    listing = client.get("/api/sessions")
    assert listing.status_code == 200
    assert {s["session_id"] for s in listing.json()} == {sess._identifier}


async def test_save_state_false_writes_nothing(isolated_home) -> None:
    with rt.Session(flow_name="nostate", save_state=False) as sess:
        await rt.call(greet)

    db_path = isolated_home / "data" / "railtracks.db"
    if db_path.exists():
        assert (
            _db_rows(isolated_home, SessionRow, SessionRow.session_id == sess._identifier)
            == []
        )
