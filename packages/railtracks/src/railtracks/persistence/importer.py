"""One-shot import of legacy JSON session files into the workspace DB.

The inverse of :mod:`railtracks.persistence.export`: takes the nested
payload shape sessions used to be saved in (``Session.payload()``) and
writes rows through the same tables the live subscriber fills. Used by
the ``railtracks migrate-json-to-sqlite`` CLI — an explicit tool, not a
runtime fallback.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel

from .models import (
    FailureRow,
    LLMCallRow,
    MessageRow,
    NodeRow,
    NodeVersionRow,
    RequestRow,
    RunRow,
    SessionRow,
    StampRow,
)


def import_legacy_session(engine: Engine, payload: dict[str, Any]) -> str | None:
    """Import one legacy session payload. Returns the session_id, or None
    if the payload has no session_id or the session already exists."""
    session_id = payload.get("session_id")
    if session_id is None:
        return None

    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        if s.get(SessionRow, session_id) is not None:
            return None

        s.add(
            SessionRow(
                session_id=session_id,
                flow_id=payload.get("flow_id"),
                flow_name=payload.get("flow_name"),
                session_name=payload.get("session_name"),
                start_time=payload.get("start_time") or 0.0,
                end_time=payload.get("end_time"),
                status=_session_status(payload),
            )
        )
        s.flush()

        for run in payload.get("runs", []):
            _import_run(s, run, session_id)

        s.commit()
    return session_id


def import_legacy_files(engine: Engine, paths: list[Path]) -> tuple[list[str], list[str]]:
    """Import several legacy JSON files. Returns (imported_ids, skipped_names)."""
    imported: list[str] = []
    skipped: list[str] = []
    for path in paths:
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            skipped.append(path.name)
            continue
        session_id = import_legacy_session(engine, payload)
        if session_id is None:
            skipped.append(path.name)
        else:
            imported.append(session_id)
    return imported, skipped


def _session_status(payload: dict[str, Any]) -> str:
    statuses = {run.get("status") for run in payload.get("runs", [])}
    if "Failed" in statuses:
        return "Failed"
    if statuses and statuses <= {"Completed"}:
        return "Completed"
    return "open"


def _import_run(s: Session, run: dict[str, Any], session_id: str) -> None:
    run_id = run["run_id"]
    s.add(
        RunRow(
            run_id=run_id,
            session_id=session_id,
            name=run.get("name"),
            status=run.get("status") or "open",
            start_time=run.get("start_time") or 0.0,
            end_time=run.get("end_time"),
        )
    )
    s.flush()

    for vertex in run.get("nodes", []):
        _import_vertex(s, vertex, run_id=run_id, session_id=session_id)
    s.flush()
    for edge in run.get("edges", []):
        _import_edge(s, edge, run_id=run_id)
    for stamp in run.get("steps", []):
        _import_stamp(s, stamp, session_id=session_id)
    s.flush()


def _import_vertex(
    s: Session, vertex: dict[str, Any], *, run_id: str, session_id: str
) -> None:
    node_uuid = vertex["identifier"]
    if s.get(NodeRow, node_uuid) is None:
        s.add(
            NodeRow(
                node_uuid=node_uuid,
                run_id=run_id,
                name=vertex.get("name") or "",
                node_type=vertex.get("node_type") or "Other",
            )
        )
        s.flush()

    # unroll the temporal parent chain into version rows, oldest first
    chain = []
    current: dict[str, Any] | None = vertex
    while current is not None:
        chain.append(current)
        current = current.get("parent")
    for version in reversed(chain):
        stamp = version.get("stamp") or {}
        s.add(
            NodeVersionRow(
                node_uuid=node_uuid,
                stamp_step=stamp.get("step", 0),
                stamp_time=stamp.get("time", 0.0),
                stamp_identifier=stamp.get("identifier", ""),
            )
        )

    internals = (vertex.get("details") or {}).get("internals") or {}
    for index, detail in enumerate(internals.get("llm_details") or []):
        _import_llm_detail(
            s, detail, node_uuid=node_uuid, session_id=session_id, call_index=index
        )


def _import_llm_detail(
    s: Session,
    detail: dict[str, Any],
    *,
    node_uuid: str,
    session_id: str,
    call_index: int,
) -> None:
    call = LLMCallRow(
        node_uuid=node_uuid,
        session_id=session_id,
        call_index=call_index,
        model_name=detail.get("model_name") or "unknown",
        model_provider=detail.get("model_provider"),
        input_tokens=detail.get("input_tokens"),
        output_tokens=detail.get("output_tokens"),
        total_cost=detail.get("total_cost"),
        system_fingerprint=detail.get("system_fingerprint"),
        latency=detail.get("latency"),
    )
    s.add(call)
    s.flush()
    assert call.call_id is not None

    for position, message in enumerate(detail.get("input") or []):
        s.add(_message_row(message, call_id=call.call_id, direction="input", position=position))
    output = detail.get("output")
    if output is not None:
        s.add(_message_row(output, call_id=call.call_id, direction="output", position=0))


def _message_row(
    message: dict[str, Any], *, call_id: int, direction: str, position: int
) -> MessageRow:
    content = message.get("content")
    if isinstance(content, str):
        kind, text, content_json = "text", content, None
    elif isinstance(content, list):
        kind, text, content_json = "tool_calls", None, content
    elif isinstance(content, dict):
        kind = "tool_response" if "result" in content else "model"
        text, content_json = None, content
    else:
        kind, text, content_json = "text", str(content), None
    return MessageRow(
        call_id=call_id,
        direction=direction,
        position=position,
        role=message.get("role") or "assistant",
        content_kind=kind,
        content_text=text,
        content_json=content_json,
    )


def _import_edge(s: Session, edge: dict[str, Any], *, run_id: str) -> None:
    details = edge.get("details") or {}
    output = details.get("output")
    status = details.get("status") or "Open"

    is_failure = (
        isinstance(output, dict)
        and {"type", "message", "traceback"} <= set(output.keys())
    )
    if output is None:
        output_kind = "open"
    elif is_failure:
        output_kind = "failure"
    else:
        output_kind = "value"

    # creation stamp = oldest entry in the temporal parent chain
    oldest = edge
    while oldest.get("parent") is not None:
        oldest = oldest["parent"]
    head_stamp = edge.get("stamp") or {}
    created_stamp = oldest.get("stamp") or {}

    s.add(
        RequestRow(
            request_id=edge["identifier"],
            run_id=run_id,
            source_node_uuid=edge.get("source"),
            sink_node_uuid=edge["target"],
            input_args_json=details.get("input_args"),
            input_kwargs_json=details.get("input_kwargs"),
            output_json=None if (is_failure or output is None) else output,
            output_kind=output_kind,
            status=status,
            created_stamp_step=created_stamp.get("step", 0),
            created_stamp_time=created_stamp.get("time", 0.0),
            stamp_step=head_stamp.get("step", 0),
            stamp_time=head_stamp.get("time", 0.0),
        )
    )
    if is_failure:
        s.flush()
        s.add(
            FailureRow(
                request_id=edge["identifier"],
                exception_type=output["type"],
                message=output["message"],
                traceback=output.get("traceback"),
            )
        )


def _import_stamp(s: Session, stamp: dict[str, Any], *, session_id: str) -> None:
    step = stamp.get("step")
    if step is None:
        return
    if s.get(StampRow, (session_id, step)) is None:
        s.add(
            StampRow(
                session_id=session_id,
                step=step,
                time=stamp.get("time", 0.0),
                identifier=stamp.get("identifier", ""),
            )
        )
