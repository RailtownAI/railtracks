"""Tests for `railtracks sessions ...` and `railtracks migrate-json-to-sqlite`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from railtracks.cli.sessions_cli import (
    migrate_json_command,
    sessions_command,
)
from railtracks.persistence.repository import SessionRepository


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RAILTRACKS_HOME", str(tmp_path))
    home = tmp_path / ".railtracks"
    home.mkdir(parents=True, exist_ok=True)
    return home


@pytest.fixture
def seeded(workspace: Path) -> SessionRepository:
    repo = SessionRepository(workspace)
    repo.start_session(
        session_id="s-1",
        flow_id="f-1",
        flow_name="demo-flow",
        session_name=None,
        start_time=100.0,
    )
    repo.end_session("s-1", end_time=105.0, status="Completed")
    repo.start_session(
        session_id="s-crashed",
        flow_id=None,
        flow_name=None,
        session_name=None,
        start_time=200.0,
    )
    return repo


def test_sessions_list(seeded, capsys) -> None:
    sessions_command(["list"])
    out = capsys.readouterr().out
    assert "s-1" in out
    assert "demo-flow" in out
    assert "Completed" in out
    # never-closed sessions surface as abandoned
    assert "abandoned" in out


def test_sessions_list_empty_workspace(workspace, capsys) -> None:
    sessions_command(["list"])
    assert "No sessions" in capsys.readouterr().out


def test_sessions_show_emits_legacy_json(seeded, capsys) -> None:
    sessions_command(["show", "s-1"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["session_id"] == "s-1"
    assert payload["flow_name"] == "demo-flow"
    assert payload["runs"] == []


def test_sessions_show_unknown_id_exits(seeded) -> None:
    with pytest.raises(SystemExit):
        sessions_command(["show", "nope"])


def test_sessions_unknown_subcommand_exits(workspace) -> None:
    with pytest.raises(SystemExit):
        sessions_command(["frobnicate"])


def test_sessions_no_subcommand_exits(workspace) -> None:
    with pytest.raises(SystemExit):
        sessions_command([])


# ── migrate-json-to-sqlite ────────────────────────────────────────────────────


LEGACY_PAYLOAD = {
    "flow_name": "Legacy Flow",
    "flow_id": "lf-1",
    "session_id": "legacy-session-1",
    "session_name": None,
    "start_time": 1000.0,
    "end_time": 1010.0,
    "runs": [
        {
            "name": "Agent",
            "run_id": "legacy-run-1",
            "status": "Completed",
            "start_time": 1000.0,
            "end_time": 1010.0,
            "nodes": [
                {
                    "identifier": "node-agent",
                    "node_type": "Agent",
                    "name": "Agent",
                    "stamp": {"step": 3, "time": 1009.0, "identifier": "done"},
                    "details": {
                        "internals": {
                            "llm_details": [
                                {
                                    "model_name": "gpt-4",
                                    "model_provider": "OpenAI",
                                    "input": [{"role": "user", "content": "hi"}],
                                    "output": {"role": "assistant", "content": "hello"},
                                    "input_tokens": 10,
                                    "output_tokens": 5,
                                    "total_cost": 0.001,
                                    "system_fingerprint": None,
                                    "latency": 0.5,
                                }
                            ]
                        }
                    },
                    "parent": {
                        "identifier": "node-agent",
                        "node_type": "Agent",
                        "name": "Agent",
                        "stamp": {"step": 0, "time": 1000.0, "identifier": "created"},
                        "details": {"internals": {}},
                        "parent": None,
                    },
                }
            ],
            "edges": [
                {
                    "identifier": "req-1",
                    "source": None,
                    "target": "node-agent",
                    "stamp": {"step": 3, "time": 1009.0, "identifier": ""},
                    "details": {
                        "input_args": ["hi"],
                        "input_kwargs": {},
                        "status": "Completed",
                        "output": {"answer": 42},
                    },
                    "parent": {
                        "identifier": "req-1",
                        "source": None,
                        "target": "node-agent",
                        "stamp": {"step": 0, "time": 1000.0, "identifier": ""},
                        "details": {
                            "input_args": ["hi"],
                            "input_kwargs": {},
                            "status": "Open",
                            "output": None,
                        },
                        "parent": None,
                    },
                },
                {
                    "identifier": "req-failed",
                    "source": "node-agent",
                    "target": "node-agent",
                    "stamp": {"step": 2, "time": 1005.0, "identifier": ""},
                    "details": {
                        "input_args": [],
                        "input_kwargs": {},
                        "status": "Failed",
                        "output": {
                            "type": "ValueError",
                            "message": "boom",
                            "traceback": "Traceback (most recent call last): ...",
                        },
                    },
                    "parent": None,
                },
            ],
            "steps": [
                {"step": 0, "time": 1000.0, "identifier": "created"},
                {"step": 3, "time": 1009.0, "identifier": "done"},
            ],
        }
    ],
}


def test_migrate_imports_legacy_file(workspace, capsys) -> None:
    legacy_dir = workspace / "data" / "sessions"
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "Legacy Flow_legacy-session-1.json").write_text(
        json.dumps(LEGACY_PAYLOAD)
    )

    migrate_json_command([])
    assert "Imported 1 session(s)" in capsys.readouterr().out

    # round-trip: the export of the import reproduces the legacy payload
    from railtracks.persistence.connection import get_engine
    from railtracks.persistence.export import legacy_session_payload

    engine = get_engine(workspace)
    try:
        rebuilt = legacy_session_payload(engine, "legacy-session-1")
    finally:
        engine.dispose()

    assert rebuilt is not None
    for key in ("flow_name", "flow_id", "session_id", "start_time", "end_time"):
        assert rebuilt[key] == LEGACY_PAYLOAD[key], key

    run = rebuilt["runs"][0]
    src = LEGACY_PAYLOAD["runs"][0]
    assert run["run_id"] == src["run_id"]
    assert run["status"] == src["status"]
    assert {n["identifier"] for n in run["nodes"]} == {"node-agent"}
    assert {e["identifier"] for e in run["edges"]} == {"req-1", "req-failed"}

    # node temporal chain survived
    vertex = run["nodes"][0]
    assert vertex["stamp"]["step"] == 3
    assert vertex["parent"]["stamp"]["step"] == 0

    # llm details survived with messages
    llm = vertex["details"]["internals"]["llm_details"][0]
    assert llm["input_tokens"] == 10
    assert llm["input"][0] == {"role": "user", "content": "hi"}
    assert llm["output"]["content"] == "hello"

    # outputs: value and failure shapes both round-trip
    edges = {e["identifier"]: e for e in run["edges"]}
    assert edges["req-1"]["details"]["output"] == {"answer": 42}
    failed = edges["req-failed"]["details"]["output"]
    assert failed["type"] == "ValueError"
    assert failed["message"] == "boom"

    # steps round-trip
    assert [s["step"] for s in run["steps"]] == [0, 3]


def test_migrate_is_idempotent(workspace, capsys) -> None:
    legacy_dir = workspace / "data" / "sessions"
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "s.json").write_text(json.dumps(LEGACY_PAYLOAD))

    migrate_json_command([])
    capsys.readouterr()
    migrate_json_command([])
    out = capsys.readouterr().out
    assert "Skipped" in out


def test_migrate_explicit_file_path(workspace, tmp_path, capsys) -> None:
    f = tmp_path / "exported.json"
    f.write_text(json.dumps(LEGACY_PAYLOAD))
    migrate_json_command([str(f)])
    assert "Imported 1 session(s)" in capsys.readouterr().out


def test_migrate_missing_path_exits(workspace) -> None:
    with pytest.raises(SystemExit):
        migrate_json_command(["/nonexistent/path"])


def test_migrate_no_files_found(workspace, capsys) -> None:
    legacy_dir = workspace / "data" / "sessions"
    legacy_dir.mkdir(parents=True)
    migrate_json_command([])
    assert "No .json files" in capsys.readouterr().out
