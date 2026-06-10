"""Round-trip tests for SessionRepository against a tmp SQLite DB."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlmodel import Session, select

from railtracks.llm import (
    AssistantMessage,
    MessageHistory,
    ToolCall,
    ToolMessage,
    ToolResponse,
    UserMessage,
)
from railtracks.persistence.models import (
    EvaluationRow,
    FailureRow,
    GuardrailRow,
    LLMCallRow,
    MessageRow,
    NodeRow,
    NodeVersionRow,
    RequestRow,
    RunRow,
    SessionRow,
    StampRow,
    ToolCallRow,
    ToolResponseRow,
)
from railtracks.persistence.repository import SessionRepository
from railtracks.utils.profiling import Stamp


def _stamp(step: int, time: float = 0.0, identifier: str = "s") -> Stamp:
    return Stamp(time=time, step=step, identifier=identifier)


@pytest.fixture
def repo(tmp_railtracks_home: Path) -> SessionRepository:
    return SessionRepository(tmp_railtracks_home)


@pytest.fixture
def seeded(repo: SessionRepository) -> SessionRepository:
    repo.start_session(
        session_id="s-1",
        flow_id="f-1",
        flow_name="demo",
        session_name=None,
        start_time=100.0,
    )
    repo.start_run(run_id="r-1", session_id="s-1", name="Agent", start_time=100.0)
    repo.upsert_node(node_uuid="n-1", run_id="r-1", name="Agent", node_type="Agent")
    return repo


def _one(repo: SessionRepository, model, *where):
    with Session(repo._engine) as s:
        stmt = select(model)
        for clause in where:
            stmt = stmt.where(clause)
        return s.exec(stmt).one()


# ----------------------------------------------------------- session lifecycle


def test_session_lifecycle(repo: SessionRepository) -> None:
    repo.start_session(
        session_id="s-1",
        flow_id="f-1",
        flow_name="demo",
        session_name="named",
        start_time=1.0,
    )
    row = _one(repo, SessionRow)
    assert row.status == "open"
    assert row.end_time is None

    repo.end_session("s-1", end_time=9.0, status="Completed")
    row = _one(repo, SessionRow)
    assert row.status == "Completed"
    assert row.end_time == 9.0


def test_run_lifecycle_and_idempotent_start(seeded: SessionRepository) -> None:
    seeded.start_run(run_id="r-1", session_id="s-1", name="Agent", start_time=100.0)
    row = _one(seeded, RunRow)
    assert row.status == "Open"

    seeded.end_run("r-1", end_time=110.0, status="Completed")
    row = _one(seeded, RunRow)
    assert row.status == "Completed"
    assert row.end_time == 110.0


# -------------------------------------------------------------------- requests


def test_request_creation_then_success(seeded: SessionRepository) -> None:
    seeded.record_request_creation(
        request_id="req-1",
        run_id="r-1",
        source_node_uuid=None,
        sink_node_uuid="n-1",
        input_args=("hello",),
        input_kwargs={"k": 1},
        stamp=_stamp(0, time=100.0),
    )
    row = _one(seeded, RequestRow)
    assert row.status == "Open"
    assert row.output_kind == "open"
    assert row.created_stamp_time == 100.0

    seeded.record_request_success(
        "req-1", output={"answer": 42}, stamp=_stamp(4, time=104.0)
    )
    row = _one(seeded, RequestRow)
    assert row.status == "Completed"
    assert row.output_kind == "value"
    assert row.output_json == {"answer": 42}
    # creation stamp survives the completion update
    assert row.created_stamp_time == 100.0
    assert row.stamp_time == 104.0


def test_request_failure_writes_failure_row(seeded: SessionRepository) -> None:
    seeded.record_request_creation(
        request_id="req-1",
        run_id="r-1",
        source_node_uuid=None,
        sink_node_uuid="n-1",
        input_args=(),
        input_kwargs={},
        stamp=_stamp(0),
    )
    try:
        raise ValueError("kaboom")
    except ValueError as e:
        seeded.record_request_failure("req-1", exception=e, stamp=_stamp(1))

    req = _one(seeded, RequestRow)
    assert req.status == "Failed"
    assert req.output_kind == "failure"

    fail = _one(seeded, FailureRow)
    assert fail.exception_type == "ValueError"
    assert fail.message == "kaboom"
    # regression for commit 6b44cf8a: traceback must be captured, not str-fallback
    assert "Traceback" in fail.traceback


def test_request_cancelled(seeded: SessionRepository) -> None:
    seeded.record_request_creation(
        request_id="req-1",
        run_id="r-1",
        source_node_uuid=None,
        sink_node_uuid="n-1",
        input_args=(),
        input_kwargs={},
        stamp=_stamp(0),
    )
    seeded.record_request_cancelled("req-1", stamp=_stamp(1))
    assert _one(seeded, RequestRow).output_kind == "cancelled"


# ----------------------------------------------------------------- node chain


def test_node_versions_append(seeded: SessionRepository) -> None:
    seeded.record_node_version("n-1", _stamp(0, identifier="created"))
    seeded.record_node_version("n-1", _stamp(3, identifier="done"))
    with Session(seeded._engine) as s:
        versions = s.exec(
            select(NodeVersionRow).order_by(NodeVersionRow.stamp_step)
        ).all()
    assert [v.stamp_identifier for v in versions] == ["created", "done"]


def test_upsert_node_is_idempotent(seeded: SessionRepository) -> None:
    seeded.upsert_node(node_uuid="n-1", run_id="r-1", name="Agent", node_type="Agent")
    with Session(seeded._engine) as s:
        assert len(s.exec(select(NodeRow)).all()) == 1


# --------------------------------------------------------------------- stamps


def test_record_stamp_idempotent(seeded: SessionRepository) -> None:
    seeded.record_stamp("s-1", _stamp(0, time=1.0, identifier="boot"))
    seeded.record_stamp("s-1", _stamp(0, time=99.0, identifier="dup"))
    row = _one(seeded, StampRow)
    assert row.identifier == "boot"


# ------------------------------------------------------------------ llm calls


def _details_with_tools() -> SimpleNamespace:
    calls = [ToolCall(identifier="t1", name="search", arguments={"q": "x"})]
    return SimpleNamespace(
        input=MessageHistory(
            [
                UserMessage("find x"),
                AssistantMessage(calls),
                ToolMessage(ToolResponse(identifier="t1", name="search", result="found")),
            ]
        ),
        output=AssistantMessage("here is x"),
        model_name="gpt-4o",
        model_provider="openai",
        input_tokens=100,
        output_tokens=20,
        total_cost=0.002,
        system_fingerprint=None,
        latency=0.7,
    )


def test_llm_call_with_messages_tools_and_response(seeded: SessionRepository) -> None:
    call_id = seeded.record_llm_call(
        _details_with_tools(), node_uuid="n-1", session_id="s-1", call_index=0
    )

    call = _one(seeded, LLMCallRow)
    assert call.call_id == call_id
    assert call.total_cost == 0.002

    with Session(seeded._engine) as s:
        messages = s.exec(
            select(MessageRow).order_by(MessageRow.direction, MessageRow.position)
        ).all()
    # 3 input + 1 output
    assert len(messages) == 4
    kinds = {(m.direction, m.content_kind) for m in messages}
    assert ("input", "tool_calls") in kinds
    assert ("input", "tool_response") in kinds
    assert ("output", "text") in kinds

    tc = _one(seeded, ToolCallRow)
    assert tc.name == "search"
    assert tc.arguments_json == {"q": "x"}
    tr = _one(seeded, ToolResponseRow)
    assert tr.result_json == "found"


def test_repeated_history_does_not_duplicate_tool_calls(
    seeded: SessionRepository,
) -> None:
    # Same ToolCall identifier appears in two consecutive calls' histories —
    # the normalized rows must be written exactly once.
    seeded.record_llm_call(
        _details_with_tools(), node_uuid="n-1", session_id="s-1", call_index=0
    )
    seeded.record_llm_call(
        _details_with_tools(), node_uuid="n-1", session_id="s-1", call_index=1
    )
    with Session(seeded._engine) as s:
        assert len(s.exec(select(ToolCallRow)).all()) == 1
        assert len(s.exec(select(ToolResponseRow)).all()) == 1
        assert len(s.exec(select(LLMCallRow)).all()) == 2


def test_orphan_tool_response_is_skipped(seeded: SessionRepository) -> None:
    details = SimpleNamespace(
        input=MessageHistory(
            [ToolMessage(ToolResponse(identifier="ghost", name="x", result="y"))]
        ),
        output=None,
        model_name="m",
        model_provider=None,
        input_tokens=None,
        output_tokens=None,
        total_cost=None,
        system_fingerprint=None,
        latency=None,
    )
    seeded.record_llm_call(details, node_uuid="n-1", session_id="s-1", call_index=0)
    with Session(seeded._engine) as s:
        assert s.exec(select(ToolResponseRow)).all() == []
        # the payload still lives on the message row
        msg = s.exec(select(MessageRow)).one()
        assert msg.content_json["result"] == "y"


# -------------------------------------------------------------------- add-ons


def test_guardrail_and_evaluation_rows(seeded: SessionRepository) -> None:
    seeded.record_guardrail(
        node_uuid="n-1", kind="pii", status="passed", details={"hits": 0}
    )
    seeded.record_evaluation(
        node_uuid="n-1", evaluator="accuracy", metric="exact", value=0.9
    )
    assert _one(seeded, GuardrailRow).details_json == {"hits": 0}
    assert _one(seeded, EvaluationRow).value == 0.9
