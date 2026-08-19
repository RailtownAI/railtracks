from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from railtracks.cli.viz_api import queries
from railtracks.cli.viz_api.models import MiddlewareSortField, SortOrder
from railtracks.cli.viz_server import app
from railtracks.observability.storage import EVENTS_DIR_ENV


@pytest.fixture(autouse=True)
def close_shared_query() -> Iterator[None]:
    queries.close_query()
    yield
    queries.close_query()


def _event(
    event_id: str,
    event_type: str,
    session_id: str,
    payload: dict[str, object],
) -> dict[str, object]:
    stamp = "2026-01-01T00:00:00+00:00"
    return {
        "event_id": event_id,
        "event_type": event_type,
        "scope_type": "session",
        "scope_id": session_id,
        "parent_scope_id": None,
        "stamp": stamp,
        "payload": {"timestamp": stamp, **payload},
    }


def _write_events(path: Path, session_id: str, *events: dict[str, object]) -> Path:
    file = path / f"{session_id}.jsonl"
    file.write_text("".join(json.dumps(event) + "\n" for event in events))
    return file


def _raising_middleware_events(session_id: str, name: str) -> list[dict[str, object]]:
    node_id = f"node-{session_id}"
    type_id = f"type-{session_id}"
    invoke_id = f"invoke-{session_id}"
    relationship = {
        "spatial_parent_type": "node_and_middleware",
        "spatial_parent_node_id": node_id,
        "parent_type": "middleware",
        "parent_middleware_type_id": type_id,
        "parent_middleware_invoke_id": invoke_id,
    }
    return [
        _event(
            f"session-{session_id}",
            "session.started",
            session_id,
            {"session_id": session_id, "flow_name": f"flow-{session_id}"},
        ),
        _event(
            f"node-{session_id}",
            "node.creation",
            session_id,
            {"node_id": node_id, "name": node_id, "node_type": "Agent"},
        ),
        _event(
            f"creation-{session_id}",
            "middleware.creation",
            session_id,
            {"middleware_type_id": type_id, "middleware_name": name},
        ),
        _event(
            f"invocation-{session_id}",
            "middleware.invocation",
            session_id,
            relationship,
        ),
        _event(
            f"failure-{session_id}",
            "middleware.failure",
            session_id,
            {
                **relationship,
                "exception_name": "RuntimeError",
                "exception_message": f"stopped-{session_id}",
            },
        ),
    ]


def test_empty_event_directory_returns_empty_api_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(EVENTS_DIR_ENV, str(tmp_path))

    response = TestClient(app).get("/api/v2/sessions")

    assert response.status_code == 200
    assert response.json() == []


def test_v2_api_allows_local_cross_origin_clients(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(EVENTS_DIR_ENV, str(tmp_path))

    response = TestClient(app).options(
        "/api/v2/sessions",
        headers={
            "Origin": "http://localhost:3001",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"


def test_connection_refreshes_when_older_file_is_added_or_removed(
    tmp_path: Path,
) -> None:
    newest = _write_events(
        tmp_path,
        "newest",
        _event("newest", "session.started", "newest", {"session_id": "newest"}),
    )
    os.utime(newest, (200, 200))

    query = queries.get_query(tmp_path)
    assert query is not None
    assert query.con.execute("SELECT COUNT(*) FROM events").fetchone() == (1,)

    older = _write_events(
        tmp_path,
        "older",
        _event("older", "session.started", "older", {"session_id": "older"}),
    )
    os.utime(older, (100, 100))

    query = queries.get_query(tmp_path)
    assert query is not None
    assert query.con.execute("SELECT COUNT(*) FROM events").fetchone() == (2,)

    older.unlink()
    query = queries.get_query(tmp_path)
    assert query is not None
    assert query.con.execute("SELECT COUNT(*) FROM events").fetchone() == (1,)


def test_blocks_only_includes_middleware_that_raised(tmp_path: Path) -> None:
    _write_events(
        tmp_path,
        "one",
        *_raising_middleware_events("one", "raises_here"),
    )
    query = queries.get_query(tmp_path)
    assert query is not None

    rows = queries.list_middleware_rows(
        query.con,
        limit=100,
        offset=0,
        blocks_only=True,
        sort_by=MiddlewareSortField.INVOCATIONS,
        order=SortOrder.DESC,
    )

    assert [(row["middleware_name"], row["blocks"]) for row in rows] == [
        ("raises_here", 1)
    ]


def test_middleware_stats_count_exact_distinct_sessions(tmp_path: Path) -> None:
    _write_events(
        tmp_path,
        "one",
        *_raising_middleware_events("one", "first"),
    )
    _write_events(
        tmp_path,
        "two",
        *_raising_middleware_events("two", "second"),
    )
    query = queries.get_query(tmp_path)
    assert query is not None

    stats = queries.get_middleware_stats(query.con)

    assert stats["total_middleware"] == 2
    assert stats["blocks"] == 2
    assert stats["sessions"] == 2
