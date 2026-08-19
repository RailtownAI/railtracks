"""Row → response-model conversion for the visualizer API.

The DuckDB layer returns plain dicts; the routes return Pydantic models. This
module is the boundary between them: the routes read as a list of endpoints,
and the row-shaping code lives here so the two concerns do not sit on top of
each other in one file.
"""

from __future__ import annotations

from typing import Any

from .models import (
    Guardrail,
    LLMContent,
    LLMTrace,
    LLMTraceStatus,
    MiddlewareBand,
    MiddlewareKind,
    MiddlewareOutcome,
    MiddlewareSummary,
    NodeStatus,
    SessionMiddleware,
    SessionStatus,
    SessionSummary,
    StreamEvent,
    TreeNode,
)


def _row_to_session_middleware(row: dict[str, Any]) -> SessionMiddleware:
    return SessionMiddleware(
        middleware_name=row["middleware_name"],
        kind=MiddlewareKind(row["kind"]),
        band=MiddlewareBand(row["band"]),
        outcome=MiddlewareOutcome(row["outcome"]),
        invocations=int(row["invocations"] or 0),
        blocks=int(row["blocks"] or 0),
        interruptions=int(row["interruptions"] or 0),
        reason=row.get("reason"),
    )


def _row_to_middleware_summary(row: dict[str, Any]) -> MiddlewareSummary:
    first_seen = row.get("first_seen")
    last_seen = row.get("last_seen")
    return MiddlewareSummary(
        middleware_name=row["middleware_name"],
        kind=MiddlewareKind(row["kind"]),
        band=MiddlewareBand(row["band"]),
        invocations=int(row["invocations"] or 0),
        decisions=int(row["decisions"] or 0),
        allows=int(row["allows"] or 0),
        transforms=int(row["transforms"] or 0),
        blocks=int(row["blocks"] or 0),
        interruptions=int(row["interruptions"] or 0),
        sessions=int(row["sessions"] or 0),
        nodes=int(row["nodes"] or 0),
        first_seen=float(first_seen) if first_seen is not None else None,
        last_seen=float(last_seen) if last_seen is not None else None,
        reason=row.get("reason"),
    )


def _row_to_summary(
    row: dict[str, Any],
    middleware: list[SessionMiddleware] | None = None,
) -> SessionSummary:
    start_time = float(row["start_time"])
    end_time = float(row["end_time"]) if row["end_time"] is not None else None
    duration = row["duration"]
    if duration is None and end_time is not None:
        duration = end_time - start_time
    return SessionSummary(
        session_id=row["session_id"],
        name=_resolve_session_name(row),
        flow_id=row.get("flow_id"),
        flow_name=row.get("flow_name"),
        entry_point_name=row.get("entry_point_name"),
        start_time=start_time,
        end_time=end_time,
        duration=float(duration) if duration is not None else None,
        # Rolled up in SQL — see _SESSION_SUMMARY_CTE. Repeating the CASE here
        # would give the status filter and the stat tiles a second definition to
        # drift from.
        status=SessionStatus(row["status"]),
        total_cost=float(row["total_cost"] or 0.0),
        input_tokens=int(row["input_tokens"] or 0),
        output_tokens=int(row["output_tokens"] or 0),
        node_count=int(row["node_count"] or 0),
        middleware=middleware or [],
    )


def _row_to_llm_trace(row: dict[str, Any]) -> LLMTrace:
    return LLMTrace(
        trace_id=row["trace_id"],
        session_id=row["session_id"],
        flow_id=row.get("flow_id"),
        flow_name=row.get("flow_name"),
        node_id=row["node_id"],
        node_name=row.get("node_name"),
        timestamp=float(row["timestamp"]),
        model_name=row.get("model_name"),
        model_provider=row.get("model_provider"),
        status=LLMTraceStatus(row.get("status") or LLMTraceStatus.SUCCESS.value),
        error_name=row.get("error_name"),
        error_message=row.get("error_message"),
        input_tokens=int(row["input_tokens"] or 0),
        output_tokens=int(row["output_tokens"] or 0),
        total_cost=float(row["total_cost"] or 0.0),
        latency_seconds=(
            float(row["latency_seconds"])
            if row.get("latency_seconds") is not None
            else None
        ),
        inputs=_to_llm_contents(row.get("inputs")),
        output=_to_llm_content(row.get("output")),
    )


def _row_to_event(row: dict[str, Any]) -> StreamEvent:
    """A raw event row as a :class:`StreamEvent`.

    ``payload`` passes through as-is. It was parsed from the stored JSON in
    :func:`queries.list_event_rows` and is whatever the writer wrote — a dict
    for every event in the registry today, but the log must render an event
    whose body is anything at all, so nothing here reshapes it.
    """
    return StreamEvent(
        event_id=row["event_id"],
        event_type=row["event_type"],
        namespace=row["namespace"],
        session_id=row["session_id"],
        scope_type=row.get("scope_type"),
        parent_scope_id=row.get("parent_scope_id"),
        timestamp=float(row["timestamp"]),
        flow_id=row.get("flow_id"),
        flow_name=row.get("flow_name"),
        node_id=row.get("node_id"),
        node_name=row.get("node_name"),
        middleware_name=row.get("middleware_name"),
        is_failure=bool(row.get("is_failure")),
        payload_bytes=int(row.get("payload_bytes") or 0),
        payload=row.get("payload"),
    )


def _resolve_session_name(row: dict[str, Any]) -> str:
    for key in ("flow_name", "session_name", "entry_point_name"):
        val = row.get(key)
        if val:
            return val
    return ""


def _node_status(row: dict[str, Any]) -> NodeStatus:
    if row["failed"]:
        return NodeStatus.FAILURE
    if row["ended_at"] is not None:
        return NodeStatus.SUCCESS
    return NodeStatus.RUNNING


def _latency(row: dict[str, Any]) -> float | None:
    """``node.destruction.duration_seconds`` when the writer populated it,
    otherwise ``ended_at - started_at`` from the invocation/destruction stamps."""
    if row.get("duration_seconds") is not None:
        return float(row["duration_seconds"])
    started = row.get("started_at")
    ended = row.get("ended_at")
    if started is not None and ended is not None:
        return max(0.0, float(ended) - float(started))
    return None


def _build_tree(
    node_rows: list[dict[str, Any]],
    guardrails_by_node: dict[str, list[dict[str, Any]]],
) -> list[TreeNode]:
    """Parent nodes and their descendants into a nested list of ``TreeNode``.

    Only Agent and Tool nodes appear in the tree. A node's parent is the value
    of ``spatial_parent_node_id`` on its invocation; nulls, or references to
    excluded nodes, become tree roots.

    Iterative post-order build: recursion would hit Python's default limit
    (~1000) on a deep session, and the log is one of the few surfaces that can
    genuinely receive arbitrary depths from user code.
    """
    tree_types = {"Agent", "Tool"}
    kept = {r["node_id"]: r for r in node_rows if r["node_type"] in tree_types}
    children_of: dict[str | None, list[str]] = {}
    for nid, row in kept.items():
        parent = row["parent_node_id"] if row["parent_node_id"] in kept else None
        children_of.setdefault(parent, []).append(nid)

    for siblings in children_of.values():
        siblings.sort(key=lambda nid: kept[nid]["created_at"] or 0.0)

    roots = children_of.get(None, [])
    # Two-pass DFS on a stack of ``(node_id, expanded)``: the first visit pushes
    # the node back with ``expanded=True`` and pushes its children, so by the
    # time it is popped again every descendant is already built. ``visited``
    # keeps a cycle from looping — the input is a DAG in practice, but the log
    # must not lock up on a malformed stream.
    built: dict[str, TreeNode] = {}
    visited: set[str] = set()
    stack: list[tuple[str, bool]] = [(nid, False) for nid in reversed(roots)]
    while stack:
        nid, expanded = stack.pop()
        if expanded:
            row = kept[nid]
            built[nid] = TreeNode(
                node_id=nid,
                display_name=row["name"] or nid,
                node_type=row["node_type"],
                latency_seconds=_latency(row) or 0.0,
                failed=bool(row["failed"]),
                guardrails=[Guardrail(**g) for g in guardrails_by_node.get(nid, [])],
                children=[built[c] for c in children_of.get(nid, []) if c in built],
            )
            continue
        if nid in visited:
            continue
        visited.add(nid)
        stack.append((nid, True))
        for child in reversed(children_of.get(nid, [])):
            if child not in visited:
                stack.append((child, False))
    return [built[nid] for nid in roots if nid in built]


def _to_llm_content(payload: Any) -> LLMContent | None:
    if payload is None:
        return None
    if isinstance(payload, dict) and "role" in payload:
        return LLMContent(role=payload["role"], content=payload.get("content"))
    return LLMContent(role="assistant", content=payload)


def _to_llm_contents(payload: Any) -> list[LLMContent]:
    if not payload:
        return []
    if isinstance(payload, list):
        return [c for c in (_to_llm_content(m) for m in payload) if c is not None]
    single = _to_llm_content(payload)
    return [single] if single else []


def _tool_input_messages(name: str, tool: dict[str, Any]) -> list[LLMContent]:
    args = tool.get("args") or []
    kwargs = tool.get("kwargs") or {}
    if not args and not kwargs:
        return []
    content: dict[str, Any] = {"name": name}
    if args:
        content["args"] = args
    if kwargs:
        content.update(kwargs)
    return [LLMContent(role="tool", content=content)]
