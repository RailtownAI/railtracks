"""Reconstruct the legacy JSON session shape from SQLite rows.

Consumed by the viz_server's ``/api/v2/sessions/{id}/full`` endpoint and
the ``railtracks sessions show --json`` CLI. The shape mirrors what
``Session.payload()`` produced when sessions were saved as JSON files,
so existing consumers keep working while they migrate to the typed
endpoints.

Known fidelity gaps (acceptable for the bridge):
- parent chains on vertices carry stamps but empty ``details`` (the
  legacy format re-serialized the full node snapshot per version)
- ``LatencyDetails`` / custom ``details`` keys beyond llm and guard
  details are not persisted relationally and so don't round-trip
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from .models import (
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
)


def legacy_session_payload(engine: Engine, session_id: str) -> dict[str, Any] | None:
    """Build the full legacy payload for one session, or None if unknown."""
    with Session(engine) as s:
        session_row = s.get(SessionRow, session_id)
        if session_row is None:
            return None

        runs = s.exec(
            select(RunRow)
            .where(RunRow.session_id == session_id)
            .order_by(RunRow.start_time)
        ).all()
        stamps_by_step = {
            st.step: st
            for st in s.exec(
                select(StampRow).where(StampRow.session_id == session_id)
            ).all()
        }

        run_payloads = [
            _run_payload(s, run, session_id, stamps_by_step) for run in runs
        ]

    return {
        "flow_name": session_row.flow_name,
        "flow_id": session_row.flow_id,
        "session_id": session_row.session_id,
        "session_name": session_row.session_name,
        "start_time": session_row.start_time,
        "end_time": session_row.end_time,
        "runs": run_payloads,
    }


def _run_payload(
    s: Session, run: RunRow, session_id: str, stamps_by_step: dict[int, StampRow]
) -> dict[str, Any]:
    nodes = s.exec(select(NodeRow).where(NodeRow.run_id == run.run_id)).all()
    requests = s.exec(
        select(RequestRow).where(RequestRow.run_id == run.run_id)
    ).all()

    vertices = []
    run_steps: set[int] = set()
    for node in nodes:
        versions = s.exec(
            select(NodeVersionRow)
            .where(NodeVersionRow.node_uuid == node.node_uuid)
            .order_by(NodeVersionRow.stamp_step)
        ).all()
        run_steps.update(v.stamp_step for v in versions)
        vertices.append(_vertex(s, node, versions, session_id))

    edges = []
    for rt in requests:
        run_steps.update((rt.created_stamp_step, rt.stamp_step))
        edges.append(_edge(s, rt))

    steps = [
        _stamp_dict(stamps_by_step[step])
        for step in sorted(run_steps)
        if step in stamps_by_step
    ]

    return {
        "name": run.name,
        "run_id": run.run_id,
        "nodes": vertices,
        "status": run.status,
        "edges": edges,
        "steps": steps,
        "start_time": run.start_time,
        "end_time": run.end_time,
    }


def _stamp_dict(stamp: StampRow) -> dict[str, Any]:
    return {"step": stamp.step, "time": stamp.time, "identifier": stamp.identifier}


def _version_stamp_dict(version: NodeVersionRow) -> dict[str, Any]:
    return {
        "step": version.stamp_step,
        "time": version.stamp_time,
        "identifier": version.stamp_identifier,
    }


def _vertex(
    s: Session, node: NodeRow, versions: list[NodeVersionRow], session_id: str
) -> dict[str, Any]:
    llm_details = _llm_details(s, node.node_uuid)
    guard_details = _guard_details(s, node.node_uuid)

    internals: dict[str, Any] = {}
    if llm_details:
        internals["llm_details"] = llm_details
    if guard_details:
        internals["guard_details"] = guard_details

    parent = None
    for version in versions[:-1]:
        parent = {
            "identifier": node.node_uuid,
            "node_type": node.node_type,
            "name": node.name,
            "stamp": _version_stamp_dict(version),
            "details": {"internals": {}},
            "parent": parent,
        }

    head_stamp = (
        _version_stamp_dict(versions[-1])
        if versions
        else {"step": 0, "time": 0.0, "identifier": ""}
    )
    return {
        "identifier": node.node_uuid,
        "node_type": node.node_type,
        "name": node.name,
        "stamp": head_stamp,
        "details": {"internals": internals},
        "parent": parent,
    }


def _llm_details(s: Session, node_uuid: str) -> list[dict[str, Any]]:
    calls = s.exec(
        select(LLMCallRow)
        .where(LLMCallRow.node_uuid == node_uuid)
        .order_by(LLMCallRow.call_index)
    ).all()

    details = []
    for call in calls:
        messages = s.exec(
            select(MessageRow)
            .where(MessageRow.call_id == call.call_id)
            .order_by(MessageRow.position)
        ).all()
        inputs = [_message_dict(m) for m in messages if m.direction == "input"]
        outputs = [_message_dict(m) for m in messages if m.direction == "output"]
        details.append(
            {
                "model_name": call.model_name,
                "model_provider": call.model_provider,
                "input": inputs,
                "output": outputs[0] if outputs else None,
                "input_tokens": call.input_tokens,
                "output_tokens": call.output_tokens,
                "total_cost": call.total_cost,
                "system_fingerprint": call.system_fingerprint,
                "latency": call.latency,
            }
        )
    return details


def _message_dict(m: MessageRow) -> dict[str, Any]:
    if m.content_kind == "text":
        content = m.content_json if m.content_json is not None else m.content_text
    else:
        content = m.content_json
    return {"role": m.role, "content": content}


def _guard_details(s: Session, node_uuid: str) -> list[Any]:
    rows = s.exec(
        select(GuardrailRow).where(GuardrailRow.node_uuid == node_uuid)
    ).all()
    return [r.details_json for r in rows if r.details_json is not None]


def _edge(s: Session, rt: RequestRow) -> dict[str, Any]:
    if rt.output_kind == "failure":
        failure = s.get(FailureRow, rt.request_id)
        output = (
            {
                "type": failure.exception_type,
                "message": failure.message,
                "traceback": failure.traceback,
            }
            if failure is not None
            else None
        )
    elif rt.output_kind == "cancelled":
        output = "Cancelled"
    else:
        output = rt.output_json

    head_stamp = {"step": rt.stamp_step, "time": rt.stamp_time, "identifier": ""}
    created_stamp = {
        "step": rt.created_stamp_step,
        "time": rt.created_stamp_time,
        "identifier": "",
    }

    parent = None
    if rt.stamp_step != rt.created_stamp_step:
        parent = {
            "source": rt.source_node_uuid,
            "target": rt.sink_node_uuid,
            "identifier": rt.request_id,
            "stamp": created_stamp,
            "details": {
                "input_args": rt.input_args_json,
                "input_kwargs": rt.input_kwargs_json,
                "status": "Open",
                "output": None,
            },
            "parent": None,
        }

    return {
        "source": rt.source_node_uuid,
        "target": rt.sink_node_uuid,
        "identifier": rt.request_id,
        "stamp": head_stamp,
        "details": {
            "input_args": rt.input_args_json,
            "input_kwargs": rt.input_kwargs_json,
            "status": rt.status,
            "output": output,
        },
        "parent": parent,
    }
