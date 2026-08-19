"""LLM traces — one row per LLM round trip, across sessions."""

from __future__ import annotations

from fastapi import APIRouter, Query

from ...io import print_status
from .. import queries
from ..models import (
    LLMTraceFilterOptions,
    LLMTracePage,
    LLMTraceSortField,
    LLMTraceStats,
    LLMTraceStatus,
    SortOrder,
)
from ..row_mapping import _row_to_llm_trace
from ._common import _events_dir

router = APIRouter(prefix="/llm-traces")


@router.get("", response_model=LLMTracePage)
async def list_llm_traces(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session_id: str | None = Query(None),
    node_id: str | None = Query(None),
    flow_name: list[str] | None = Query(None),
    node_name: list[str] | None = Query(None),
    model_name: list[str] | None = Query(None),
    status: list[LLMTraceStatus] | None = Query(None),
    since: float | None = Query(None),
    until: float | None = Query(None),
    sort_by: LLMTraceSortField = Query(LLMTraceSortField.TIMESTAMP),
    order: SortOrder = Query(SortOrder.DESC),
) -> LLMTracePage:
    """List LLM calls across sessions, newest first by default.

    One row per round trip, whether it returned or raised. Filters and sort
    apply server-side, before paging. Repeating any list filter ORs its
    values; separate filters AND.
    """
    print_status(
        f"GET /api/llm-traces limit={limit} offset={offset} "
        f"session_id={session_id} node_id={node_id} "
        f"flow_name={flow_name} node_name={node_name} model_name={model_name} "
        f"status={status} since={since} until={until} "
        f"sort_by={sort_by.value} order={order.value}"
    )
    events_dir = _events_dir()
    if not events_dir.exists():
        return LLMTracePage(rows=[], total=0, limit=limit, offset=offset)

    q = queries.get_query(events_dir)
    rows = queries.list_llm_trace_rows(
        q.con,
        limit=limit,
        offset=offset,
        session_id=session_id,
        node_id=node_id,
        flow_names=flow_name,
        node_names=node_name,
        model_names=model_name,
        statuses=status,
        since=since,
        until=until,
        sort_by=sort_by,
        order=order,
    )
    total = queries.count_llm_trace_rows(
        q.con,
        session_id=session_id,
        node_id=node_id,
        flow_names=flow_name,
        node_names=node_name,
        model_names=model_name,
        statuses=status,
        since=since,
        until=until,
    )
    return LLMTracePage(
        rows=[_row_to_llm_trace(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/stats", response_model=LLMTraceStats)
async def get_llm_trace_stats(
    session_id: str | None = Query(None),
    node_id: str | None = Query(None),
    flow_name: list[str] | None = Query(None),
    node_name: list[str] | None = Query(None),
    model_name: list[str] | None = Query(None),
    status: list[LLMTraceStatus] | None = Query(None),
    since: float | None = Query(None),
    until: float | None = Query(None),
) -> LLMTraceStats:
    """Roll-up across every LLM call matching the filters, ignoring paging."""
    print_status(
        f"GET /api/llm-traces/stats session_id={session_id} node_id={node_id} "
        f"flow_name={flow_name} node_name={node_name} model_name={model_name} "
        f"status={status} since={since} until={until}"
    )
    events_dir = _events_dir()
    if not events_dir.exists():
        return LLMTraceStats()

    q = queries.get_query(events_dir)
    stats = queries.get_llm_trace_stats(
        q.con,
        session_id=session_id,
        node_id=node_id,
        flow_names=flow_name,
        node_names=node_name,
        model_names=model_name,
        statuses=status,
        since=since,
        until=until,
    )
    avg_latency = stats.get("avg_latency_seconds")
    max_latency = stats.get("max_latency_seconds")
    return LLMTraceStats(
        total_calls=int(stats.get("total_calls") or 0),
        failed_calls=int(stats.get("failed_calls") or 0),
        input_tokens=int(stats.get("input_tokens") or 0),
        output_tokens=int(stats.get("output_tokens") or 0),
        total_cost=float(stats.get("total_cost") or 0.0),
        avg_latency_seconds=float(avg_latency) if avg_latency is not None else None,
        max_latency_seconds=float(max_latency) if max_latency is not None else None,
    )


@router.get("/filters", response_model=LLMTraceFilterOptions)
async def get_llm_trace_filter_options() -> LLMTraceFilterOptions:
    """Every value the ``/api/llm-traces`` filters can take."""
    print_status("GET /api/llm-traces/filters")
    events_dir = _events_dir()
    if not events_dir.exists():
        return LLMTraceFilterOptions()

    q = queries.get_query(events_dir)
    return LLMTraceFilterOptions(**queries.list_llm_trace_filter_options(q.con))
