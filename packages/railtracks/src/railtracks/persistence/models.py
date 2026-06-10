"""SQLModel tables for railtracks session persistence.

Row classes are named with a `Row` suffix to avoid clashes with the
domain types (`Session`, `Node`, `Message`, `LLMCall`, ...). One table
per concept; structured fields are columns, open-ended payloads are
JSON columns.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Column, ForeignKey, Index
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class SessionRow(SQLModel, table=True):
    __tablename__ = "sessions"

    session_id: str = Field(primary_key=True)
    flow_id: str = Field(index=True)
    flow_name: str | None = None
    session_name: str | None = None
    start_time: float
    end_time: float | None = None
    status: str


class RunRow(SQLModel, table=True):
    __tablename__ = "runs"

    run_id: str = Field(primary_key=True)
    session_id: str = Field(foreign_key="sessions.session_id", index=True)
    name: str | None = None
    status: str
    start_time: float
    end_time: float | None = None


class NodeRow(SQLModel, table=True):
    __tablename__ = "nodes"

    node_uuid: str = Field(primary_key=True)
    run_id: str = Field(foreign_key="runs.run_id", index=True)
    name: str
    node_type: str
    open_args_json: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )


class NodeVersionRow(SQLModel, table=True):
    """One row per immutable snapshot in the LinkedNode.parent chain."""

    __tablename__ = "node_versions"

    version_id: int | None = Field(default=None, primary_key=True)
    node_uuid: str = Field(foreign_key="nodes.node_uuid", index=True)
    stamp_step: int
    stamp_time: float
    stamp_identifier: str


class StampRow(SQLModel, table=True):
    """Logical-clock entries from StampManager. (session_id, step) composite PK."""

    __tablename__ = "stamps"

    session_id: str = Field(
        primary_key=True, foreign_key="sessions.session_id"
    )
    step: int = Field(primary_key=True)
    time: float
    identifier: str


class RequestRow(SQLModel, table=True):
    __tablename__ = "requests"

    request_id: str = Field(primary_key=True)
    run_id: str = Field(foreign_key="runs.run_id", index=True)
    source_node_uuid: str | None = Field(
        default=None, foreign_key="nodes.node_uuid", index=True
    )
    sink_node_uuid: str = Field(foreign_key="nodes.node_uuid", index=True)
    input_args_json: list[Any] | None = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    input_kwargs_json: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    output_json: Any | None = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    output_kind: str  # "value" | "failure" | "cancelled" | "open"
    status: str
    stamp_step: int
    stamp_time: float
    parent_request_id: str | None = Field(
        default=None, sa_column=Column(ForeignKey("requests.request_id"), nullable=True)
    )


class FailureRow(SQLModel, table=True):
    __tablename__ = "failures"

    request_id: str = Field(primary_key=True, foreign_key="requests.request_id")
    exception_type: str
    message: str
    traceback: str | None = None


class LLMCallRow(SQLModel, table=True):
    __tablename__ = "llm_calls"
    __table_args__ = (
        Index("ix_llm_calls_session_model", "session_id", "model_name"),
    )

    call_id: int | None = Field(default=None, primary_key=True)
    node_uuid: str = Field(foreign_key="nodes.node_uuid", index=True)
    # Denormalized session_id to keep the cross-session "LLM Traces" query
    # (issue #239) on a single indexed scan instead of a 4-table join.
    session_id: str = Field(foreign_key="sessions.session_id", index=True)
    call_index: int
    model_name: str
    model_provider: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_cost: float | None = None
    system_fingerprint: str | None = None
    latency: float | None = None


class MessageRow(SQLModel, table=True):
    __tablename__ = "messages"

    message_id: int | None = Field(default=None, primary_key=True)
    call_id: int = Field(foreign_key="llm_calls.call_id", index=True)
    direction: str  # "input" | "output"
    position: int  # order within the input history; 0 for output
    role: str
    content_kind: str  # "text" | "tool_calls" | "tool_response" | "model"
    content_text: str | None = None
    content_json: Any | None = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )


class ToolCallRow(SQLModel, table=True):
    __tablename__ = "tool_calls"

    tool_call_id: str = Field(primary_key=True)
    message_id: int = Field(foreign_key="messages.message_id", index=True)
    name: str = Field(index=True)
    arguments_json: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )


class ToolResponseRow(SQLModel, table=True):
    __tablename__ = "tool_responses"

    tool_call_id: str = Field(primary_key=True, foreign_key="tool_calls.tool_call_id")
    name: str
    result_json: Any | None = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )


# First-class add-on tables hanging off nodes. Promoted out of the
# `node.details` dict so guardrails/evals/memory/middleware can be
# queried without walking nested JSON.


class GuardrailRow(SQLModel, table=True):
    __tablename__ = "guardrails"

    guardrail_id: int | None = Field(default=None, primary_key=True)
    node_uuid: str = Field(foreign_key="nodes.node_uuid", index=True)
    kind: str
    status: str | None = None
    details_json: Any | None = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    stamp_time: float | None = None


class EvaluationRow(SQLModel, table=True):
    __tablename__ = "evaluations"

    eval_id: int | None = Field(default=None, primary_key=True)
    node_uuid: str = Field(foreign_key="nodes.node_uuid", index=True)
    evaluator: str = Field(index=True)
    metric: str | None = None
    value: float | None = None
    details_json: Any | None = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )


class MemoryRow(SQLModel, table=True):
    __tablename__ = "memory"

    memory_id: int | None = Field(default=None, primary_key=True)
    node_uuid: str = Field(foreign_key="nodes.node_uuid", index=True)
    kind: str
    key: str | None = None
    value_json: Any | None = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    stamp_time: float | None = None


class MiddlewareTraceRow(SQLModel, table=True):
    __tablename__ = "middleware_traces"

    trace_id: int | None = Field(default=None, primary_key=True)
    node_uuid: str = Field(foreign_key="nodes.node_uuid", index=True)
    middleware_name: str
    phase: str | None = None
    details_json: Any | None = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    stamp_time: float | None = None


__all__ = [
    "SessionRow",
    "RunRow",
    "NodeRow",
    "NodeVersionRow",
    "StampRow",
    "RequestRow",
    "FailureRow",
    "LLMCallRow",
    "MessageRow",
    "ToolCallRow",
    "ToolResponseRow",
    "GuardrailRow",
    "EvaluationRow",
    "MemoryRow",
    "MiddlewareTraceRow",
]
