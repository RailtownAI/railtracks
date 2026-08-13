"""FastAPI routes for the visualizer, backed by the event-stream query layer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from railtracks.paths import resolve_railtracks_home

from ..io import print_error, print_status
from . import queries
from .models import (
    GraphEdge,
    GraphNode,
    Guardrail,
    LLMContent,
    NodeDetail,
    NodeRef,
    NodeStatus,
    SessionDetail,
    SessionGraph,
    SessionStatus,
    SessionSummary,
    TracePage,
    TraceRow,
    TreeNode,
)

router = APIRouter(prefix="/api")


def _events_dir() -> Path:
    return resolve_railtracks_home() / "data"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/sessions", response_model=list[SessionSummary])
async def list_sessions() -> list[SessionSummary]:
    """List every session in the events home, most recent first."""
    print_status("GET /api/sessions")
    events_dir = _events_dir()
    if not events_dir.exists():
        return []

    try:
        q = queries.get_query(events_dir)
        rows = queries.list_session_rows(q.con)
    except Exception as e:  # noqa: BLE001 - keep the endpoint resilient
        print_error(f"list_sessions query failed: {e}")
        raise HTTPException(status_code=500, detail="failed to query events") from e

    return [_row_to_summary(r) for r in rows]


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str) -> SessionDetail:
    """Full session payload: summary + prepared tree + default selection."""
    print_status(f"GET /api/sessions/{session_id}")
    events_dir = _events_dir()
    if not events_dir.exists():
        raise HTTPException(status_code=404, detail="no events home")

    q = queries.get_query(events_dir)
    summary_row = queries.get_session_row(q.con, session_id)
    if summary_row is None:
        raise HTTPException(status_code=404, detail="session not found")
    node_rows = queries.list_session_node_rows(q.con, session_id)
    guardrails_by_node = queries.list_guardrails_by_node(q.con, session_id)

    tree = _build_tree(node_rows, guardrails_by_node)
    default = NodeRef(node_id=tree[0].node_id) if tree else None

    return SessionDetail(
        **_row_to_summary(summary_row).model_dump(),
        tree=tree,
        default_selection=default,
    )


@router.get(
    "/sessions/{session_id}/nodes/{node_id}",
    response_model=NodeDetail,
)
async def get_node_detail(session_id: str, node_id: str) -> NodeDetail:
    """Inputs, outputs, cost, latency and guardrails for one node."""
    print_status(f"GET /api/sessions/{session_id}/nodes/{node_id}")
    events_dir = _events_dir()
    if not events_dir.exists():
        raise HTTPException(status_code=404, detail="no events home")

    q = queries.get_query(events_dir)
    node_row = queries.get_node_row(q.con, session_id, node_id)
    if node_row is None:
        raise HTTPException(status_code=404, detail="node not found")

    node_rows = queries.list_session_node_rows(q.con, session_id)
    this_row = next((r for r in node_rows if r["node_id"] == node_id), None)
    latency = _latency(this_row) if this_row else None
    guardrails = queries.list_guardrails_by_node(q.con, session_id).get(node_id, [])

    node_type = node_row["node_type"]
    name = node_row["name"] or node_type

    if node_type == "Agent":
        final, totals = queries.get_agent_llm_details(q.con, session_id, node_id)
        inputs = _to_llm_contents(final["message_input"]) if final else []
        output = _to_llm_content(final["output"]) if final else None
        model_name = final["model_name"] if final else None
        model_provider = final["model_provider"] if final else None
        tool_output: Any = None
    elif node_type == "Tool":
        tool = queries.get_tool_io(q.con, session_id, node_id)
        inputs = _tool_input_messages(name, tool) if tool else []
        tool_output = tool["response"] if tool else None
        output = None
        model_name = None
        model_provider = None
        totals = {"input_tokens": 0, "output_tokens": 0, "total_cost": 0.0}
    else:
        inputs = []
        output = None
        tool_output = None
        model_name = None
        model_provider = None
        totals = {"input_tokens": 0, "output_tokens": 0, "total_cost": 0.0}

    return NodeDetail(
        node_id=node_id,
        node_type=node_type,
        name=name,
        status=_node_status(this_row) if this_row else NodeStatus.SUCCESS,
        inputs=inputs,
        output=output,
        tool_output=tool_output,
        model_name=model_name,
        model_provider=model_provider,
        total_cost=float(totals["total_cost"] or 0.0),
        input_tokens=int(totals["input_tokens"] or 0),
        output_tokens=int(totals["output_tokens"] or 0),
        guardrails=[Guardrail(**g) for g in guardrails],
        latency_seconds=latency,
    )


@router.get("/traces", response_model=TracePage)
async def list_traces(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session_id: str | None = Query(None),
    node_id: str | None = Query(None),
    flow_name: list[str] | None = Query(None),
    model_name: list[str] | None = Query(None),
) -> TracePage:
    """List LLM calls across sessions, newest first.

    Filters (``flow_name``, ``session_id``, ``node_id``, ``model_name``) apply
    server-side, before paging. Repeating ``flow_name`` / ``model_name`` ORs the
    values. An offset past the end returns no rows, not an error.

    Returns a :class:`TracePage`, so ``total`` reflects every matching row and a
    client can size its pager without over-fetching to probe for a next page.
    """
    print_status(
        f"GET /api/traces limit={limit} offset={offset} "
        f"session_id={session_id} node_id={node_id} "
        f"flow_name={flow_name} model_name={model_name}"
    )
    events_dir = _events_dir()
    if not events_dir.exists():
        return TracePage(rows=[], total=0, limit=limit, offset=offset)

    q = queries.get_query(events_dir)
    rows = queries.list_trace_rows(
        q.con,
        limit=limit,
        offset=offset,
        session_id=session_id,
        node_id=node_id,
        flow_names=flow_name,
        model_names=model_name,
    )
    total = queries.count_trace_rows(
        q.con,
        session_id=session_id,
        node_id=node_id,
        flow_names=flow_name,
        model_names=model_name,
    )
    return TracePage(
        rows=[_row_to_trace(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/sessions/{session_id}/graph", response_model=SessionGraph)
async def get_session_graph(session_id: str) -> SessionGraph:
    """React-Flow-shaped graph for the session — nodes and parent→child edges."""
    print_status(f"GET /api/sessions/{session_id}/graph")
    events_dir = _events_dir()
    if not events_dir.exists():
        raise HTTPException(status_code=404, detail="no events home")

    q = queries.get_query(events_dir)
    summary_row = queries.get_session_row(q.con, session_id)
    if summary_row is None:
        raise HTTPException(status_code=404, detail="session not found")
    node_rows = queries.list_session_node_rows(q.con, session_id)
    llm_totals = {
        r["node_id"]: r for r in queries.list_llm_totals_by_node(q.con, session_id)
    }
    guardrails_by_node = queries.list_guardrails_by_node(q.con, session_id)

    graph_nodes: list[GraphNode] = []
    graph_edges: list[GraphEdge] = []
    for n in node_rows:
        totals = llm_totals.get(n["node_id"], {})
        graph_nodes.append(
            GraphNode(
                id=n["node_id"],
                type=n["node_type"],
                label=n["name"] or n["node_type"],
                time=n["started_at"] or n["created_at"],
                model_name=totals.get("model_name"),
                model_provider=totals.get("model_provider"),
                total_cost=float(totals.get("total_cost") or 0.0),
                input_tokens=int(totals.get("input_tokens") or 0),
                output_tokens=int(totals.get("output_tokens") or 0),
                latency_seconds=_latency(n),
                status=_node_status(n),
                guardrails=[
                    Guardrail(**g) for g in guardrails_by_node.get(n["node_id"], [])
                ],
            )
        )
        graph_edges.append(
            GraphEdge(
                id=f"e:{n['parent_node_id'] or 'root'}->{n['node_id']}",
                source=n["parent_node_id"],
                target=n["node_id"],
            )
        )

    return SessionGraph(session_id=session_id, nodes=graph_nodes, edges=graph_edges)


# ---------------------------------------------------------------------------
# Row → model helpers
# ---------------------------------------------------------------------------


def _row_to_summary(row: dict[str, Any]) -> SessionSummary:
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
        status=_roll_up_status(row["raw_status"], end_time is not None),
        total_cost=float(row["total_cost"] or 0.0),
        input_tokens=int(row["input_tokens"] or 0),
        output_tokens=int(row["output_tokens"] or 0),
        node_count=int(row["node_count"] or 0),
    )


def _row_to_trace(row: dict[str, Any]) -> TraceRow:
    return TraceRow(
        trace_id=row["trace_id"],
        session_id=row["session_id"],
        flow_id=row.get("flow_id"),
        flow_name=row.get("flow_name"),
        node_id=row["node_id"],
        node_name=row.get("node_name"),
        timestamp=float(row["timestamp"]),
        model_name=row.get("model_name"),
        model_provider=row.get("model_provider"),
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


def _resolve_session_name(row: dict[str, Any]) -> str:
    for key in ("flow_name", "session_name", "entry_point_name"):
        val = row.get(key)
        if val:
            return val
    return ""


def _roll_up_status(raw_status: str | None, completed: bool) -> SessionStatus:
    if raw_status is None:
        return SessionStatus.RUNNING if not completed else SessionStatus.COMPLETED
    status = raw_status.lower()
    if status == "success":
        return SessionStatus.COMPLETED
    if status == "failure":
        return SessionStatus.FAILED
    return SessionStatus.RUNNING


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
    """
    tree_types = {"Agent", "Tool"}
    kept = {r["node_id"]: r for r in node_rows if r["node_type"] in tree_types}
    children_of: dict[str | None, list[str]] = {}
    for nid, row in kept.items():
        parent = row["parent_node_id"] if row["parent_node_id"] in kept else None
        children_of.setdefault(parent, []).append(nid)

    for siblings in children_of.values():
        siblings.sort(key=lambda nid: kept[nid]["created_at"] or 0.0)

    visited: set[str] = set()

    def build(nid: str) -> TreeNode:
        visited.add(nid)
        row = kept[nid]
        children: list[TreeNode] = []
        for child in children_of.get(nid, []):
            if child in visited:
                continue
            children.append(build(child))
        return TreeNode(
            node_id=nid,
            display_name=row["name"] or nid,
            node_type=row["node_type"],
            latency_seconds=_latency(row) or 0.0,
            failed=bool(row["failed"]),
            guardrails=[Guardrail(**g) for g in guardrails_by_node.get(nid, [])],
            children=children,
        )

    return [build(nid) for nid in children_of.get(None, [])]


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
