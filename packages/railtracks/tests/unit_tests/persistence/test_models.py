"""Smoke tests for the SQLModel row types.

These tests don't exercise migrations or the repository — they confirm
that each row class round-trips through SQLAlchemy with the expected
columns, FKs are enforced, and JSON columns accept nested payloads.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from railtracks.persistence.models import (
    EvaluationRow,
    FailureRow,
    GuardrailRow,
    LLMCallRow,
    MemoryRow,
    MessageRow,
    MiddlewareTraceRow,
    NodeRow,
    NodeVersionRow,
    RequestRow,
    RunRow,
    SessionRow,
    StampRow,
    ToolCallRow,
    ToolResponseRow,
)


def _seed_session(db_session: Session) -> tuple[str, str, str]:
    # SQLAlchemy doesn't reorder inserts across tables without an explicit
    # relationship graph, so flush in FK order.
    db_session.add(
        SessionRow(
            session_id="s1",
            flow_id="f1",
            flow_name="demo",
            session_name="run-a",
            start_time=1.0,
            end_time=None,
            status="open",
        )
    )
    db_session.flush()
    db_session.add(RunRow(run_id="r1", session_id="s1", status="open", start_time=1.0))
    db_session.flush()
    db_session.add(NodeRow(node_uuid="n1", run_id="r1", name="Agent", node_type="Agent"))
    db_session.commit()
    return "s1", "r1", "n1"


def test_session_run_node_chain(db_session: Session) -> None:
    _seed_session(db_session)
    nodes = db_session.exec(select(NodeRow)).all()
    assert len(nodes) == 1
    assert nodes[0].run_id == "r1"


def test_node_requires_existing_run(db_session: Session) -> None:
    db_session.add(NodeRow(node_uuid="orphan", run_id="missing", name="x", node_type="Tool"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_request_self_reference_and_node_endpoints(db_session: Session) -> None:
    _seed_session(db_session)
    parent = RequestRow(
        request_id="req-parent",
        run_id="r1",
        source_node_uuid=None,
        sink_node_uuid="n1",
        output_kind="open",
        status="Open",
        stamp_step=0,
        stamp_time=1.0,
    )
    child = RequestRow(
        request_id="req-child",
        run_id="r1",
        source_node_uuid="n1",
        sink_node_uuid="n1",
        output_kind="value",
        status="Completed",
        stamp_step=1,
        stamp_time=2.0,
        parent_request_id="req-parent",
        output_json={"value": 42},
    )
    db_session.add_all([parent, child])
    db_session.commit()

    fetched = db_session.exec(
        select(RequestRow).where(RequestRow.parent_request_id == "req-parent")
    ).one()
    assert fetched.output_json == {"value": 42}


def test_failure_attaches_to_request(db_session: Session) -> None:
    _seed_session(db_session)
    db_session.add(
        RequestRow(
            request_id="req-fail",
            run_id="r1",
            sink_node_uuid="n1",
            output_kind="failure",
            status="Failed",
            stamp_step=1,
            stamp_time=2.0,
        )
    )
    db_session.flush()
    db_session.add(
        FailureRow(
            request_id="req-fail",
            exception_type="ValueError",
            message="bad input",
            traceback="Traceback (...)",
        )
    )
    db_session.commit()

    got = db_session.exec(select(FailureRow)).one()
    assert got.traceback == "Traceback (...)"


def test_failure_requires_request(db_session: Session) -> None:
    db_session.add(
        FailureRow(request_id="missing", exception_type="X", message="y")
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_llm_call_messages_tool_call_tool_response(db_session: Session) -> None:
    _seed_session(db_session)
    call = LLMCallRow(
        node_uuid="n1",
        session_id="s1",
        call_index=0,
        model_name="gpt-4",
        model_provider="openai",
        input_tokens=100,
        output_tokens=50,
        total_cost=0.01,
        latency=1.5,
    )
    db_session.add(call)
    db_session.commit()
    db_session.refresh(call)

    msg_in = MessageRow(
        call_id=call.call_id,
        direction="input",
        position=0,
        role="user",
        content_kind="text",
        content_text="hello",
    )
    msg_out = MessageRow(
        call_id=call.call_id,
        direction="output",
        position=0,
        role="assistant",
        content_kind="tool_calls",
        content_json=[{"id": "t1", "name": "search", "args": {"q": "x"}}],
    )
    db_session.add_all([msg_in, msg_out])
    db_session.commit()
    db_session.refresh(msg_out)

    db_session.add(
        ToolCallRow(
            tool_call_id="t1",
            message_id=msg_out.message_id,
            name="search",
            arguments_json={"q": "x"},
        )
    )
    db_session.flush()
    db_session.add(ToolResponseRow(tool_call_id="t1", name="search", result_json={"hits": [1, 2]}))
    db_session.commit()

    fetched = db_session.exec(
        select(LLMCallRow).where(LLMCallRow.session_id == "s1")
    ).one()
    assert fetched.model_name == "gpt-4"
    assert fetched.total_cost == 0.01

    response = db_session.exec(select(ToolResponseRow)).one()
    assert response.result_json == {"hits": [1, 2]}


def test_composite_stamp_pk(db_session: Session) -> None:
    _seed_session(db_session)
    db_session.add_all([
        StampRow(session_id="s1", step=0, time=1.0, identifier="boot"),
        StampRow(session_id="s1", step=1, time=2.0, identifier="step-1"),
    ])
    db_session.commit()

    with pytest.raises(IntegrityError):
        db_session.add(StampRow(session_id="s1", step=0, time=3.0, identifier="dup"))
        db_session.commit()


def test_node_version_chain(db_session: Session) -> None:
    _seed_session(db_session)
    db_session.add_all([
        NodeVersionRow(node_uuid="n1", stamp_step=0, stamp_time=1.0, stamp_identifier="created"),
        NodeVersionRow(node_uuid="n1", stamp_step=1, stamp_time=2.0, stamp_identifier="completed"),
    ])
    db_session.commit()

    versions = db_session.exec(
        select(NodeVersionRow).where(NodeVersionRow.node_uuid == "n1").order_by(NodeVersionRow.stamp_step)
    ).all()
    assert [v.stamp_identifier for v in versions] == ["created", "completed"]


def test_addon_tables_hang_off_node(db_session: Session) -> None:
    _seed_session(db_session)
    db_session.add_all([
        GuardrailRow(node_uuid="n1", kind="pii", status="passed", details_json={"ok": True}),
        EvaluationRow(node_uuid="n1", evaluator="accuracy", metric="exact_match", value=1.0),
        MemoryRow(node_uuid="n1", kind="scratch", key="x", value_json={"v": 1}),
        MiddlewareTraceRow(node_uuid="n1", middleware_name="trace", phase="before"),
    ])
    db_session.commit()
    assert db_session.exec(select(GuardrailRow)).one().details_json == {"ok": True}
    assert db_session.exec(select(EvaluationRow)).one().value == 1.0
    assert db_session.exec(select(MemoryRow)).one().value_json == {"v": 1}
    assert db_session.exec(select(MiddlewareTraceRow)).one().phase == "before"
