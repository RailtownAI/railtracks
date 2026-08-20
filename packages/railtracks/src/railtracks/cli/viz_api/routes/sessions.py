"""Sessions, node details, and the per-session graph."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Path as PathParam

from railtracks.query import EventQuery

from .. import queries
from ..models import (
    GraphEdge,
    GraphNode,
    Guardrail,
    NodeDetail,
    NodeRef,
    NodeStatus,
    SessionDetail,
    SessionFilterOptions,
    SessionGraph,
    SessionPage,
    SessionSortField,
    SessionStats,
    SortOrder,
)
from ..row_mapping import (
    _build_tree,
    _latency,
    _node_status,
    _row_to_session_middleware,
    _row_to_summary,
    _to_llm_content,
    _to_llm_contents,
    _tool_input_messages,
)
from ._common import (
    _SESSION_ID_PATTERN,
    QueryFailureRoute,
    get_query_or_404,
    get_query_or_none,
)

router = APIRouter(prefix="/sessions", tags=["sessions"], route_class=QueryFailureRoute)


@router.get("", response_model=SessionPage)
async def list_sessions(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    flow_name: list[str] | None = Query(None),
    entry_point_name: list[str] | None = Query(None),
    status: list[str] | None = Query(None),
    since: float | None = Query(None),
    until: float | None = Query(None),
    sort_by: SessionSortField = Query(SessionSortField.START_TIME),
    order: SortOrder = Query(SortOrder.DESC),
    q: EventQuery | None = Depends(get_query_or_none),
) -> SessionPage:
    """List sessions in the events home, most recent first.

    Filters apply server-side. Repeating a param ORs its values; separate
    params AND. ``since`` / ``until`` are unix seconds bounding ``start_time``.
    """
    if q is None:
        return SessionPage(rows=[], total=0, limit=limit, offset=offset)

    filters = {
        "flow_names": flow_name,
        "entry_point_names": entry_point_name,
        "statuses": status,
        "since": since,
        "until": until,
    }
    rows = queries.list_session_rows(
        q.con,
        **filters,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        order=order,
    )
    middleware = queries.list_middleware_by_session(
        q.con, [r["session_id"] for r in rows]
    )

    total = queries.count_session_rows(q.con, **filters)
    return SessionPage(
        rows=[
            _row_to_summary(
                r,
                [
                    _row_to_session_middleware(m)
                    for m in middleware.get(r["session_id"], [])
                ],
            )
            for r in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/stats", response_model=SessionStats)
async def get_session_stats(
    flow_name: list[str] | None = Query(None),
    entry_point_name: list[str] | None = Query(None),
    status: list[str] | None = Query(None),
    since: float | None = Query(None),
    until: float | None = Query(None),
    q: EventQuery | None = Depends(get_query_or_none),
) -> SessionStats:
    """Roll-up across every session matching the filters.

    Takes the same filter params as ``/api/v2/sessions``.
    """
    if q is None:
        return SessionStats()

    stats = queries.get_session_stats(
        q.con,
        flow_names=flow_name,
        entry_point_names=entry_point_name,
        statuses=status,
        since=since,
        until=until,
    )
    return SessionStats(
        total_runs=int(stats.get("total_runs") or 0),
        successes=int(stats.get("successes") or 0),
        failures=int(stats.get("failures") or 0),
        blocked=int(stats.get("blocked") or 0),
        running=int(stats.get("running") or 0),
        input_tokens=int(stats.get("input_tokens") or 0),
        output_tokens=int(stats.get("output_tokens") or 0),
        total_cost=float(stats.get("total_cost") or 0.0),
    )


@router.get("/filters", response_model=SessionFilterOptions)
async def get_session_filter_options(
    q: EventQuery | None = Depends(get_query_or_none),
) -> SessionFilterOptions:
    """Values the session filters accept, across every session in the stream."""
    if q is None:
        return SessionFilterOptions()
    return SessionFilterOptions(**queries.list_session_filter_options(q.con))


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: str = PathParam(..., pattern=_SESSION_ID_PATTERN),
    q: EventQuery = Depends(get_query_or_404),
) -> SessionDetail:
    """Full session payload: summary + prepared tree + default selection."""
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


@router.get("/{session_id}/nodes/{node_id}", response_model=NodeDetail)
async def get_node_detail(
    session_id: str = PathParam(..., pattern=_SESSION_ID_PATTERN),
    node_id: str = PathParam(...),
    q: EventQuery = Depends(get_query_or_404),
) -> NodeDetail:
    """Inputs, outputs, cost, latency and guardrails for one node."""
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


@router.get("/{session_id}/graph", response_model=SessionGraph)
async def get_session_graph(
    session_id: str = PathParam(..., pattern=_SESSION_ID_PATTERN),
    q: EventQuery = Depends(get_query_or_404),
) -> SessionGraph:
    """React-Flow-shaped graph for the session — nodes and parent→child edges."""
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
