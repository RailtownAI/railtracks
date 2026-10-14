from __future__ import annotations

import inspect
import json
import os
import threading
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest
from fastapi.testclient import TestClient
from railtracks.cli.viz_api import queries
from railtracks.cli.viz_api._logging import set_debug
from railtracks.cli.viz_api.models import MiddlewareSortField, SortOrder
from railtracks.cli.viz_api.routes._common import get_query_or_404, get_query_or_none
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
    *,
    stamp: str = "2026-01-01T00:00:00+00:00",
) -> dict[str, object]:
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


def _verifier_decision_events(
    session_id: str, name: str, action: str, *, overridden: bool = False
) -> list[dict[str, object]]:
    """Events for one verifier invocation, ending in a given decision.

    Mirrors ``_raising_middleware_events``'s node-and-middleware relationship,
    but for the decision path rather than a raw exception: a
    ``middleware.verifier.pre.response`` event carrying a ``decision`` payload
    (the shape ``pre_verifier``/``post_verifier`` actually emit), which
    queries/middleware.py normalizes onto the guard vocabulary.

    A ``"decline"`` additionally reports the ``VerifierRejectedError`` the
    wrapper's own generic ``middleware.failure`` carries — a verifier's node
    never runs to produce its own ``node.failure``/``llm.failure`` — and a
    failed ``session.completed``, matching what the Blocked/Failed split in
    sessions.py reads.
    """
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
    events = [
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
            f"decision-{session_id}",
            "middleware.verifier.pre.response",
            session_id,
            {**relationship, "decision": {"action": action, "overridden": overridden}},
        ),
    ]
    if action == "decline":
        events.append(
            _event(
                f"failure-{session_id}",
                "middleware.failure",
                session_id,
                {
                    **relationship,
                    "exception_name": "VerifierRejectedError",
                    "exception_message": f"rejected-{session_id}",
                },
            )
        )
        status = "failure"
    else:
        events.append(
            _event(
                f"response-{session_id}",
                "middleware.response",
                session_id,
                {**relationship, "response": None},
            )
        )
        status = "success"
    events.append(
        _event(
            f"completed-{session_id}",
            "session.completed",
            session_id,
            {"session_id": session_id, "status": status},
        )
    )
    return events


def _verifier_stack_events(
    session_id: str,
    outer_name: str,
    verifier_name: str,
    *,
    crash: bool,
) -> list[dict[str, object]]:
    """Events for a plain wrapper stacked *around* a verifier that fails.

    Both middleware share one node, so the exception unwinds through the
    verifier first and then the outer wrapper -- same exception message, two
    separate ``middleware.failure`` events, as a real run produces. A
    ``decline`` reports through ``middleware.verifier.pre.response``, the same
    as :func:`_verifier_decision_events`; a ``crash`` (``approve_fn`` itself
    raising) reports through ``middleware.verifier.pre.failure`` instead, since
    there is no decision to report. Either way, the verifier's own node never
    ran, so there is no ``node.failure``/``llm.failure`` for either failure to
    inherit -- exercising exactly the gap ``callee_failures``' verifier branch
    closes.
    """
    node_id = f"node-{session_id}"
    message = f"stopped-{session_id}"
    outer = {
        "spatial_parent_type": "node_and_middleware",
        "spatial_parent_node_id": node_id,
        "parent_type": "middleware",
        "parent_middleware_type_id": f"type-outer-{session_id}",
        "parent_middleware_invoke_id": f"invoke-outer-{session_id}",
    }
    verifier = {
        "spatial_parent_type": "node_and_middleware",
        "spatial_parent_node_id": node_id,
        "parent_type": "middleware",
        "parent_middleware_type_id": f"type-verifier-{session_id}",
        "parent_middleware_invoke_id": f"invoke-verifier-{session_id}",
    }
    events = [
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
            f"creation-outer-{session_id}",
            "middleware.creation",
            session_id,
            {
                "middleware_type_id": outer["parent_middleware_type_id"],
                "middleware_name": outer_name,
            },
        ),
        _event(
            f"creation-verifier-{session_id}",
            "middleware.creation",
            session_id,
            {
                "middleware_type_id": verifier["parent_middleware_type_id"],
                "middleware_name": verifier_name,
            },
        ),
        _event(
            f"invocation-outer-{session_id}", "middleware.invocation", session_id, outer
        ),
        _event(
            f"invocation-verifier-{session_id}",
            "middleware.invocation",
            session_id,
            verifier,
        ),
    ]
    if crash:
        events.append(
            _event(
                f"verifier-failure-{session_id}",
                "middleware.verifier.pre.failure",
                session_id,
                {
                    **verifier,
                    "exception_name": "ValueError",
                    "exception_message": message,
                },
            )
        )
    else:
        events.append(
            _event(
                f"decision-{session_id}",
                "middleware.verifier.pre.response",
                session_id,
                {**verifier, "decision": {"action": "decline"}},
            )
        )
    events.append(
        _event(
            f"failure-verifier-{session_id}",
            "middleware.failure",
            session_id,
            {
                **verifier,
                "exception_name": "ValueError" if crash else "VerifierRejectedError",
                "exception_message": message,
            },
        )
    )
    events.append(
        _event(
            f"failure-outer-{session_id}",
            "middleware.failure",
            session_id,
            {**outer, "exception_name": "ValueError", "exception_message": message},
        )
    )
    return events


def test_empty_event_directory_returns_empty_api_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(EVENTS_DIR_ENV, str(tmp_path))

    response = TestClient(app).get("/api/v2/sessions")

    assert response.status_code == 200
    assert response.json() == {"rows": [], "total": 0, "limit": 50, "offset": 0}


def test_sessions_are_sorted_and_paginated_before_middleware_loading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(EVENTS_DIR_ENV, str(tmp_path))
    for position, session_id in enumerate(("oldest", "middle", "newest"), start=1):
        stamp = f"2026-01-0{position}T00:00:00+00:00"
        _write_events(
            tmp_path,
            session_id,
            _event(
                session_id,
                "session.started",
                session_id,
                {
                    "session_id": session_id,
                    "flow_name": session_id,
                    "entry_point_name": f"entry-{position}",
                },
                stamp=stamp,
            ),
        )

    response = TestClient(app).get(
        "/api/v2/sessions",
        params={
            "limit": 1,
            "offset": 1,
            "sort_by": "start_time",
            "order": "desc",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["limit"] == 1
    assert body["offset"] == 1
    assert [row["session_id"] for row in body["rows"]] == ["middle"]


@pytest.mark.parametrize("origin", ("http://localhost:3001", "http://127.0.0.1:4317"))
def test_v2_api_allows_loopback_cross_origin_clients(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, origin: str
) -> None:
    monkeypatch.setenv(EVENTS_DIR_ENV, str(tmp_path))

    response = TestClient(app).options(
        "/api/v2/sessions",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


@pytest.mark.parametrize(
    "origin",
    (
        "https://untrusted.example",
        "http://localhost.evil.example:3001",
        "null",
    ),
)
def test_v2_api_rejects_untrusted_cross_origin_clients(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, origin: str
) -> None:
    monkeypatch.setenv(EVENTS_DIR_ENV, str(tmp_path))
    client = TestClient(app)

    preflight = client.options(
        "/api/v2/sessions",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    response = client.get("/api/v2/sessions", headers={"Origin": origin})

    assert preflight.status_code == 400
    assert "access-control-allow-origin" not in preflight.headers
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


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


def test_connection_reads_appends_without_refresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    file = _write_events(
        tmp_path,
        "session",
        _event("event-one", "session.started", "session", {"session_id": "session"}),
    )
    query = queries.get_query(tmp_path)
    assert query is not None

    def unexpected_refresh() -> None:
        pytest.fail("an append to an existing path must not rebuild DuckDB views")

    monkeypatch.setattr(query, "refresh", unexpected_refresh)
    with file.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                _event(
                    "event-two",
                    "session.completed",
                    "session",
                    {"session_id": "session", "status": "success"},
                )
            )
            + "\n"
        )

    same_query = queries.get_query(tmp_path)

    assert same_query is query
    assert query.con.execute("SELECT COUNT(*) FROM events").fetchone() == (2,)


def test_connection_reads_same_path_replacement_without_refresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    file = _write_events(
        tmp_path,
        "session",
        _event("old-event", "session.started", "session", {"session_id": "session"}),
    )
    original_stat = file.stat()
    original_size = original_stat.st_size
    query = queries.get_query(tmp_path)
    assert query is not None

    def unexpected_refresh() -> None:
        pytest.fail("a same-path replacement must not rebuild DuckDB views")

    monkeypatch.setattr(query, "refresh", unexpected_refresh)
    _write_events(
        tmp_path,
        "session",
        _event("new-event", "session.started", "session", {"session_id": "session"}),
    )
    assert file.stat().st_size == original_size
    os.utime(
        file,
        ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
    )

    same_query = queries.get_query(tmp_path)

    assert same_query is query
    assert query.con.execute("SELECT event_id FROM events").fetchall() == [
        ("new-event",)
    ]


def test_connection_closes_on_empty_store_and_reopens_for_a_new_file(
    tmp_path: Path,
) -> None:
    file = _write_events(
        tmp_path,
        "first",
        _event("first", "session.started", "first", {"session_id": "first"}),
    )
    first_query = queries.get_query(tmp_path)
    assert first_query is not None

    file.unlink()
    assert queries.get_query(tmp_path) is None
    with pytest.raises(duckdb.ConnectionException):
        first_query.con.execute("SELECT 1")

    _write_events(
        tmp_path,
        "second",
        _event("second", "session.started", "second", {"session_id": "second"}),
    )
    second_query = queries.get_query(tmp_path)

    assert second_query is not None
    assert second_query is not first_query
    assert second_query.con.execute("SELECT event_id FROM events").fetchall() == [
        ("second",)
    ]


def test_api_dependency_and_queries_share_the_event_loop_thread(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(EVENTS_DIR_ENV, str(tmp_path))
    query = SimpleNamespace(con=object())
    thread_ids: dict[str, int] = {}

    def fake_get_query(_events_dir: Path):
        thread_ids["dependency"] = threading.get_ident()
        return query

    def fake_list_session_rows(*_args: object, **_kwargs: object):
        thread_ids["list"] = threading.get_ident()
        return []

    def fake_list_middleware(*_args: object, **_kwargs: object):
        thread_ids["middleware"] = threading.get_ident()
        return {}

    def fake_count_session_rows(*_args: object, **_kwargs: object):
        thread_ids["count"] = threading.get_ident()
        return 0

    monkeypatch.setattr(queries, "get_query", fake_get_query)
    monkeypatch.setattr(queries, "list_session_rows", fake_list_session_rows)
    monkeypatch.setattr(queries, "list_middleware_by_session", fake_list_middleware)
    monkeypatch.setattr(queries, "count_session_rows", fake_count_session_rows)

    response = TestClient(app).get("/api/v2/sessions")

    assert response.status_code == 200
    assert len(set(thread_ids.values())) == 1


def test_both_query_dependencies_remain_async() -> None:
    assert inspect.iscoroutinefunction(get_query_or_none)
    assert inspect.iscoroutinefunction(get_query_or_404)


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


def test_verifier_decisions_classify_as_verifier_kind(tmp_path: Path) -> None:
    _write_events(
        tmp_path,
        "one",
        *_verifier_decision_events("one", "approve_charge", "accept"),
    )
    query = queries.get_query(tmp_path)
    assert query is not None

    rows = queries.list_middleware_rows(
        query.con,
        limit=100,
        offset=0,
        sort_by=MiddlewareSortField.INVOCATIONS,
        order=SortOrder.DESC,
    )

    assert [
        row["kind"] for row in rows if row["middleware_name"] == "approve_charge"
    ] == ["verifier"]


def test_verifier_actions_normalize_to_guard_vocabulary(tmp_path: Path) -> None:
    _write_events(
        tmp_path, "allow", *_verifier_decision_events("allow", "allower", "accept")
    )
    _write_events(
        tmp_path,
        "transform",
        *_verifier_decision_events("transform", "overrider", "accept", overridden=True),
    )
    _write_events(
        tmp_path, "block", *_verifier_decision_events("block", "decliner", "decline")
    )
    query = queries.get_query(tmp_path)
    assert query is not None

    rows = {
        row["middleware_name"]: row
        for row in queries.list_middleware_rows(
            query.con,
            limit=100,
            offset=0,
            sort_by=MiddlewareSortField.INVOCATIONS,
            order=SortOrder.DESC,
        )
    }

    assert (rows["allower"]["allows"], rows["allower"]["blocks"]) == (1, 0)
    assert (rows["overrider"]["transforms"], rows["overrider"]["blocks"]) == (1, 0)
    assert rows["decliner"]["blocks"] == 1


def test_verifier_reject_marks_session_blocked(tmp_path: Path) -> None:
    _write_events(
        tmp_path,
        "rejected",
        *_verifier_decision_events("rejected", "gatekeeper", "decline"),
    )
    query = queries.get_query(tmp_path)
    assert query is not None

    rows = queries.list_session_rows(query.con)

    assert [row["status"] for row in rows if row["session_id"] == "rejected"] == [
        "Blocked"
    ]


@pytest.mark.parametrize("crash", [False, True], ids=["decline", "crash"])
def test_wrapper_outside_a_failing_verifier_is_not_marked_blocked(
    tmp_path: Path, crash: bool
) -> None:
    """A verifier's own decline/crash never lets its node run, so there is no
    node.failure/llm.failure to excuse a plain middleware wrapped around it --
    the exact gap that let a stacked wrapper misread as having blocked the
    call it merely sat outside of.
    """
    _write_events(
        tmp_path,
        "one",
        *_verifier_stack_events("one", "outer_wrapper", "the_verifier", crash=crash),
    )
    query = queries.get_query(tmp_path)
    assert query is not None

    rows = {
        row["middleware_name"]: row
        for row in queries.list_middleware_rows(
            query.con,
            limit=100,
            offset=0,
            sort_by=MiddlewareSortField.INVOCATIONS,
            order=SortOrder.DESC,
        )
    }

    assert (
        rows["outer_wrapper"]["blocks"],
        rows["outer_wrapper"]["interruptions"],
    ) == (
        0,
        1,
    )
    assert (rows["the_verifier"]["blocks"], rows["the_verifier"]["interruptions"]) == (
        1,
        0,
    )


def test_query_failures_emit_structured_error_logs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv(EVENTS_DIR_ENV, str(tmp_path))
    _write_events(
        tmp_path,
        "broken",
        _event(
            "broken",
            "session.started",
            "broken",
            {"session_id": "broken", "flow_name": "broken"},
        ),
    )

    def fail(*_args: object, **_kwargs: object) -> list[dict[str, object]]:
        raise RuntimeError("duckdb exploded")

    set_debug(False)
    monkeypatch.setattr(queries, "list_session_rows", fail)

    response = TestClient(app).get("/api/v2/sessions")

    assert response.status_code == 500
    payload = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert payload["level"] == "error"
    assert payload["event"] == "query_failed"
    assert payload["path"] == "/api/v2/sessions"
    assert payload["error_type"] == "RuntimeError"
    assert payload["error"] == "duckdb exploded"


def _llm_session_events(
    session_id: str,
    node_id: str,
    llm_id: str,
    total_cost: float | None,
) -> list[dict[str, object]]:
    """Minimal event stream for a session with one LLM response.

    ``total_cost`` is passed through unchanged so callers can write either a
    known value or ``None`` (unpriced model) and verify how the API renders it.
    """
    stamp = "2026-01-01T00:00:00+00:00"
    return [
        _event(
            f"started-{session_id}",
            "session.started",
            session_id,
            {"session_id": session_id, "flow_name": f"flow-{session_id}"},
            stamp=stamp,
        ),
        _event(
            f"node-{session_id}",
            "node.creation",
            session_id,
            {"node_id": node_id, "name": "agent", "node_type": "Agent"},
            stamp=stamp,
        ),
        _event(
            f"llm-creation-{session_id}",
            "llm.creation",
            session_id,
            {"llm_id": llm_id, "model_provider": "openai", "model_name": "gpt-4o"},
            stamp=stamp,
        ),
        _event(
            f"llm-response-{session_id}",
            "llm.response",
            session_id,
            {
                "spatial_parent_node_id": node_id,
                "parent_llm_type_id": llm_id,
                "input_tokens": 10,
                "output_tokens": 5,
                "total_cost": total_cost,
                "message_input": [{"role": "user", "content": "hi"}],
                "output": {"role": "assistant", "content": "hello"},
            },
            stamp=stamp,
        ),
        _event(
            f"completed-{session_id}",
            "session.completed",
            session_id,
            {"status": "success", "duration_seconds": 1.0},
            stamp=stamp,
        ),
    ]


def test_null_cost_surfaces_as_null_in_session_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed pricing lookup must not silently render as $0.00.

    When every LLM call in a session has total_cost=NULL (unpriced model),
    the session-list endpoint must return total_cost=null, not 0.0.
    """
    monkeypatch.setenv(EVENTS_DIR_ENV, str(tmp_path))
    _write_events(
        tmp_path,
        "unpriced",
        *_llm_session_events("unpriced", "node-u", "llm-u", total_cost=None),
    )

    response = TestClient(app).get("/api/v2/sessions")

    assert response.status_code == 200
    rows = response.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["total_cost"] is None, (
        f"expected null for unpriced model, got {rows[0]['total_cost']!r}"
    )


def test_zero_cost_surfaces_as_zero_in_session_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A genuinely free call must still render as $0.00, not null."""
    monkeypatch.setenv(EVENTS_DIR_ENV, str(tmp_path))
    _write_events(
        tmp_path,
        "free",
        *_llm_session_events("free", "node-f", "llm-f", total_cost=0.0),
    )

    response = TestClient(app).get("/api/v2/sessions")

    assert response.status_code == 200
    rows = response.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["total_cost"] == 0.0, (
        f"expected 0.0 for a free call, got {rows[0]['total_cost']!r}"
    )


def test_null_cost_surfaces_as_null_in_llm_traces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """total_cost=null must pass through the LLM-traces endpoint unchanged."""
    monkeypatch.setenv(EVENTS_DIR_ENV, str(tmp_path))
    _write_events(
        tmp_path,
        "trace-unpriced",
        *_llm_session_events("trace-unpriced", "node-t", "llm-t", total_cost=None),
    )

    response = TestClient(app).get("/api/v2/llm-traces")

    assert response.status_code == 200
    rows = response.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["total_cost"] is None, (
        f"expected null for unpriced trace, got {rows[0]['total_cost']!r}"
    )


def _llm_failure_session_events(
    session_id: str,
    node_id: str,
    llm_id: str,
) -> list[dict[str, object]]:
    """Minimal event stream for a session with one LLM failure.

    The failure row has no total_cost in the raw event; the CTE should
    return 0.0 (nothing is billed for a call that never came back).
    """
    stamp = "2026-01-01T00:00:00+00:00"
    return [
        _event(
            f"started-{session_id}",
            "session.started",
            session_id,
            {"session_id": session_id, "flow_name": f"flow-{session_id}"},
            stamp=stamp,
        ),
        _event(
            f"node-{session_id}",
            "node.creation",
            session_id,
            {"node_id": node_id, "name": "agent", "node_type": "Agent"},
            stamp=stamp,
        ),
        _event(
            f"llm-creation-{session_id}",
            "llm.creation",
            session_id,
            {"llm_id": llm_id, "model_provider": "openai", "model_name": "gpt-4o"},
            stamp=stamp,
        ),
        _event(
            f"llm-failure-{session_id}",
            "llm.failure",
            session_id,
            {
                "spatial_parent_node_id": node_id,
                "parent_llm_type_id": llm_id,
                "message_input": [{"role": "user", "content": "hi"}],
                "exception_name": "TimeoutError",
                "exception_message": "request timed out",
            },
            stamp=stamp,
        ),
    ]


def test_failed_call_cost_surfaces_as_zero_in_llm_traces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed LLM call must render total_cost as 0.0, not null.

    Nothing is billed for a call that never returned a response. Returning
    null here would be misleading -- it reads as "pricing unknown" when the
    correct meaning is "$0.00 was charged."
    """
    monkeypatch.setenv(EVENTS_DIR_ENV, str(tmp_path))
    _write_events(
        tmp_path,
        "failed-call",
        *_llm_failure_session_events("failed-call", "node-f", "llm-f"),
    )

    response = TestClient(app).get("/api/v2/llm-traces")

    assert response.status_code == 200
    rows = response.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["total_cost"] == 0.0, (
        f"expected 0.0 for failed call, got {rows[0]['total_cost']!r}"
    )
