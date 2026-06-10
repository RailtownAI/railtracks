"""Write-side repository for railtracks session persistence.

Each public method opens a short transaction against the workspace
SQLite DB. The repository is the single place that threads generated
keys (``llm_calls.call_id``, ``messages.message_id``) into child rows;
the value-level conversion lives in :mod:`railtracks.persistence.mappers`.

Schema creation: ``SessionRepository`` ensures tables exist on first
construction via ``SQLModel.metadata.create_all`` — cheap (IF NOT
EXISTS) and keeps the runtime path independent of the Alembic CLI.
Alembic owns *evolution* of existing databases.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlmodel import Session, SQLModel, select

from railtracks.built_nodes.concrete import RequestDetails
from railtracks.llm import Message, ToolCall, ToolResponse
from railtracks.state.node import LinkedNode
from railtracks.state.request import Failure, RequestTemplate
from railtracks.state.serialize import encode_failure
from railtracks.utils.profiling import Stamp

from .connection import get_engine
from .mappers import (
    classify_message,
    jsonable,
    linked_node_to_rows,
    llm_details_to_call_row,
    output_kind_of,
    request_to_rows,
)
from .models import (
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


class SessionRepository:
    def __init__(self, railtracks_home: Path | None = None):
        self._engine = get_engine(railtracks_home)
        SQLModel.metadata.create_all(self._engine)

    # ------------------------------------------------------------------
    # session / run lifecycle
    # ------------------------------------------------------------------

    def start_session(
        self,
        *,
        session_id: str,
        flow_id: str,
        flow_name: str | None,
        session_name: str | None,
        start_time: float,
    ) -> None:
        with Session(self._engine) as s:
            s.add(
                SessionRow(
                    session_id=session_id,
                    flow_id=flow_id,
                    flow_name=flow_name,
                    session_name=session_name,
                    start_time=start_time,
                    status="open",
                )
            )
            s.commit()

    def end_session(
        self, session_id: str, *, end_time: float, status: str
    ) -> None:
        with Session(self._engine) as s:
            row = s.get(SessionRow, session_id)
            if row is None:
                return
            row.end_time = end_time
            row.status = status
            s.add(row)
            s.commit()

    def start_run(
        self,
        *,
        run_id: str,
        session_id: str,
        name: str | None,
        start_time: float,
    ) -> None:
        with Session(self._engine) as s:
            if s.get(RunRow, run_id) is not None:
                return
            s.add(
                RunRow(
                    run_id=run_id,
                    session_id=session_id,
                    name=name,
                    status="Open",
                    start_time=start_time,
                )
            )
            s.commit()

    def end_run(self, run_id: str, *, end_time: float, status: str) -> None:
        with Session(self._engine) as s:
            row = s.get(RunRow, run_id)
            if row is None:
                return
            row.end_time = end_time
            row.status = status
            s.add(row)
            s.commit()

    # ------------------------------------------------------------------
    # nodes
    # ------------------------------------------------------------------

    def upsert_node(
        self,
        *,
        node_uuid: str,
        run_id: str,
        name: str,
        node_type: str,
    ) -> None:
        with Session(self._engine) as s:
            if s.get(NodeRow, node_uuid) is None:
                s.add(
                    NodeRow(
                        node_uuid=node_uuid,
                        run_id=run_id,
                        name=name,
                        node_type=node_type,
                    )
                )
                s.commit()

    def record_node_version(self, node_uuid: str, stamp: Stamp) -> None:
        with Session(self._engine) as s:
            s.add(
                NodeVersionRow(
                    node_uuid=node_uuid,
                    stamp_step=stamp.step,
                    stamp_time=stamp.time,
                    stamp_identifier=stamp.identifier,
                )
            )
            s.commit()

    def persist_linked_node(self, ln: LinkedNode, *, run_id: str) -> None:
        """Batch helper: upsert the node and append every version in the
        temporal chain that isn't recorded yet."""
        node_row, version_rows = linked_node_to_rows(ln, run_id)
        with Session(self._engine) as s:
            if s.get(NodeRow, node_row.node_uuid) is None:
                s.add(node_row)
                s.flush()
            existing_steps = {
                v.stamp_step
                for v in s.exec(
                    select(NodeVersionRow).where(
                        NodeVersionRow.node_uuid == node_row.node_uuid
                    )
                ).all()
            }
            for v in version_rows:
                if v.stamp_step not in existing_steps:
                    s.add(v)
            s.commit()

    # ------------------------------------------------------------------
    # requests
    # ------------------------------------------------------------------

    def record_request_creation(
        self,
        *,
        request_id: str,
        run_id: str,
        source_node_uuid: str | None,
        sink_node_uuid: str,
        input_args: tuple | list,
        input_kwargs: dict,
        stamp: Stamp,
    ) -> None:
        with Session(self._engine) as s:
            if s.get(RequestRow, request_id) is not None:
                return
            s.add(
                RequestRow(
                    request_id=request_id,
                    run_id=run_id,
                    source_node_uuid=source_node_uuid,
                    sink_node_uuid=sink_node_uuid,
                    input_args_json=jsonable(list(input_args)),
                    input_kwargs_json=jsonable(input_kwargs),
                    output_kind="open",
                    status="Open",
                    created_stamp_step=stamp.step,
                    created_stamp_time=stamp.time,
                    stamp_step=stamp.step,
                    stamp_time=stamp.time,
                )
            )
            s.commit()

    def record_request_success(
        self, request_id: str, *, output: Any, stamp: Stamp
    ) -> None:
        with Session(self._engine) as s:
            row = s.get(RequestRow, request_id)
            if row is None:
                return
            row.output_json = jsonable(output)
            row.output_kind = output_kind_of(output)
            row.status = "Completed"
            row.stamp_step = stamp.step
            row.stamp_time = stamp.time
            s.add(row)
            s.commit()

    def record_request_failure(
        self, request_id: str, *, exception: Exception, stamp: Stamp
    ) -> None:
        encoded = encode_failure(Failure(exception))
        with Session(self._engine) as s:
            row = s.get(RequestRow, request_id)
            if row is not None:
                row.output_kind = "failure"
                row.status = "Failed"
                row.stamp_step = stamp.step
                row.stamp_time = stamp.time
                s.add(row)
            if s.get(FailureRow, request_id) is None and row is not None:
                s.add(
                    FailureRow(
                        request_id=request_id,
                        exception_type=encoded["type"],
                        message=encoded["message"],
                        traceback=encoded["traceback"],
                    )
                )
            s.commit()

    def persist_request(self, rt: RequestTemplate, *, run_id: str) -> None:
        """Batch helper: map a RequestTemplate (latest version) to its row,
        replacing any earlier state of the same request."""
        request_row, failure_row = request_to_rows(rt, run_id)
        with Session(self._engine) as s:
            existing = s.get(RequestRow, request_row.request_id)
            if existing is not None:
                for field in (
                    "output_json",
                    "output_kind",
                    "status",
                    "stamp_step",
                    "stamp_time",
                ):
                    setattr(existing, field, getattr(request_row, field))
                s.add(existing)
            else:
                s.add(request_row)
            s.flush()
            if failure_row is not None and s.get(FailureRow, failure_row.request_id) is None:
                s.add(failure_row)
            s.commit()

    def record_request_cancelled(self, request_id: str, *, stamp: Stamp) -> None:
        with Session(self._engine) as s:
            row = s.get(RequestRow, request_id)
            if row is None:
                return
            row.output_kind = "cancelled"
            row.status = "Completed"
            row.stamp_step = stamp.step
            row.stamp_time = stamp.time
            s.add(row)
            s.commit()

    # ------------------------------------------------------------------
    # stamps
    # ------------------------------------------------------------------

    def record_stamp(self, session_id: str, stamp: Stamp) -> None:
        with Session(self._engine) as s:
            if s.get(StampRow, (session_id, stamp.step)) is None:
                s.add(
                    StampRow(
                        session_id=session_id,
                        step=stamp.step,
                        time=stamp.time,
                        identifier=stamp.identifier,
                    )
                )
                s.commit()

    # ------------------------------------------------------------------
    # LLM calls
    # ------------------------------------------------------------------

    def record_llm_call(
        self,
        details: RequestDetails,
        *,
        node_uuid: str,
        session_id: str,
        call_index: int,
    ) -> int:
        """Insert the call row plus its input history and output messages.

        Returns the generated call_id.
        """
        call_row = llm_details_to_call_row(
            details,
            node_uuid=node_uuid,
            session_id=session_id,
            call_index=call_index,
        )
        with Session(self._engine) as s:
            s.add(call_row)
            s.flush()
            assert call_row.call_id is not None

            for position, message in enumerate(details.input or []):
                self._insert_message(
                    s, message, call_id=call_row.call_id,
                    direction="input", position=position,
                )
            if details.output is not None:
                self._insert_message(
                    s, details.output, call_id=call_row.call_id,
                    direction="output", position=0,
                )
            s.commit()
            return call_row.call_id

    def _insert_message(
        self,
        s: Session,
        message: Message,
        *,
        call_id: int,
        direction: str,
        position: int,
    ) -> None:
        kind, text, content_json, tool_calls, tool_response = classify_message(
            message
        )
        msg_row = MessageRow(
            call_id=call_id,
            direction=direction,
            position=position,
            role=message.role.value,
            content_kind=kind,
            content_text=text,
            content_json=content_json,
        )
        s.add(msg_row)
        s.flush()
        assert msg_row.message_id is not None

        # Message history repeats across calls: the same ToolCall identifier
        # shows up in one call's output and the next call's input. The first
        # occurrence wins; later ones only keep the message-level JSON copy.
        for tc in tool_calls:
            self._insert_tool_call(s, tc, message_id=msg_row.message_id)
        if tool_response is not None:
            self._insert_tool_response(s, tool_response)

    def _insert_tool_call(
        self, s: Session, tc: ToolCall, *, message_id: int
    ) -> None:
        if s.get(ToolCallRow, tc.identifier) is None:
            s.add(
                ToolCallRow(
                    tool_call_id=tc.identifier,
                    message_id=message_id,
                    name=tc.name,
                    arguments_json=jsonable(tc.arguments),
                )
            )

    def _insert_tool_response(self, s: Session, tr: ToolResponse) -> None:
        # FK requires the matching tool_call row; a history that begins
        # mid-conversation can carry responses to calls we never saw. The
        # message row's content_json keeps the payload either way.
        if s.get(ToolCallRow, tr.identifier) is None:
            return
        if s.get(ToolResponseRow, tr.identifier) is None:
            s.add(
                ToolResponseRow(
                    tool_call_id=tr.identifier,
                    name=tr.name,
                    result_json=jsonable(tr.result),
                )
            )

    # ------------------------------------------------------------------
    # add-ons
    # ------------------------------------------------------------------

    def record_guardrail(
        self,
        *,
        node_uuid: str,
        kind: str,
        status: str | None = None,
        details: Any = None,
        stamp_time: float | None = None,
    ) -> None:
        with Session(self._engine) as s:
            s.add(
                GuardrailRow(
                    node_uuid=node_uuid,
                    kind=kind,
                    status=status,
                    details_json=jsonable(details),
                    stamp_time=stamp_time,
                )
            )
            s.commit()

    def record_evaluation(
        self,
        *,
        node_uuid: str,
        evaluator: str,
        metric: str | None = None,
        value: float | None = None,
        details: Any = None,
    ) -> None:
        with Session(self._engine) as s:
            s.add(
                EvaluationRow(
                    node_uuid=node_uuid,
                    evaluator=evaluator,
                    metric=metric,
                    value=value,
                    details_json=jsonable(details),
                )
            )
            s.commit()
