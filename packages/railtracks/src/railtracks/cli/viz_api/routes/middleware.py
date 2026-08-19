"""Middleware — one row per (name, kind, band), rolled up."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from railtracks.query import EventQuery

from ...io import print_status
from .. import queries
from ..models import (
    MiddlewareFilterOptions,
    MiddlewarePage,
    MiddlewareSortField,
    MiddlewareStats,
    SortOrder,
)
from ..row_mapping import _row_to_middleware_summary
from ._common import QueryFailureRoute, get_query_or_none

router = APIRouter(prefix="/middleware", route_class=QueryFailureRoute)


@router.get("", response_model=MiddlewarePage)
async def list_middleware(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session_id: str | None = Query(None),
    node_id: str | None = Query(None),
    kind: list[str] | None = Query(None),
    band: list[str] | None = Query(None),
    middleware_name: list[str] | None = Query(None),
    flow_name: list[str] | None = Query(None),
    blocks_only: bool = Query(False),
    include_internal: bool = Query(False),
    since: float | None = Query(None),
    until: float | None = Query(None),
    sort_by: MiddlewareSortField = Query(MiddlewareSortField.INVOCATIONS),
    order: SortOrder = Query(SortOrder.DESC),
    q: EventQuery | None = Depends(get_query_or_none),
) -> MiddlewarePage:
    """List middleware, one row per ``(name, kind, band)``, busiest first.

    ``include_internal`` surfaces the framework's own ``_observe_middleware``
    and ``_llm_observe``, which are hidden by default. ``blocks_only`` narrows
    to middleware that blocked at least once.
    """
    print_status(
        f"GET /api/middleware limit={limit} offset={offset} "
        f"session_id={session_id} node_id={node_id} kind={kind} band={band} "
        f"middleware_name={middleware_name} flow_name={flow_name} "
        f"blocks_only={blocks_only} include_internal={include_internal} "
        f"since={since} until={until} "
        f"sort_by={sort_by.value} order={order.value}"
    )
    if q is None:
        return MiddlewarePage(rows=[], total=0, limit=limit, offset=offset)

    filters: dict[str, Any] = {
        "session_id": session_id,
        "node_id": node_id,
        "kinds": kind,
        "bands": band,
        "middleware_names": middleware_name,
        "flow_names": flow_name,
        "blocks_only": blocks_only,
        "include_internal": include_internal,
        "since": since,
        "until": until,
    }
    rows = queries.list_middleware_rows(
        q.con, limit=limit, offset=offset, sort_by=sort_by, order=order, **filters
    )
    total = queries.count_middleware_rows(q.con, **filters)
    return MiddlewarePage(
        rows=[_row_to_middleware_summary(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/stats", response_model=MiddlewareStats)
async def get_middleware_stats(
    session_id: str | None = Query(None),
    node_id: str | None = Query(None),
    kind: list[str] | None = Query(None),
    band: list[str] | None = Query(None),
    middleware_name: list[str] | None = Query(None),
    flow_name: list[str] | None = Query(None),
    blocks_only: bool = Query(False),
    include_internal: bool = Query(False),
    since: float | None = Query(None),
    until: float | None = Query(None),
    q: EventQuery | None = Depends(get_query_or_none),
) -> MiddlewareStats:
    """Roll-up across every middleware matching the filters, ignoring paging."""
    print_status(
        f"GET /api/middleware/stats session_id={session_id} node_id={node_id} "
        f"kind={kind} band={band} middleware_name={middleware_name} "
        f"flow_name={flow_name} blocks_only={blocks_only} "
        f"include_internal={include_internal} since={since} until={until}"
    )
    if q is None:
        return MiddlewareStats()

    stats = queries.get_middleware_stats(
        q.con,
        session_id=session_id,
        node_id=node_id,
        kinds=kind,
        bands=band,
        middleware_names=middleware_name,
        flow_names=flow_name,
        blocks_only=blocks_only,
        include_internal=include_internal,
        since=since,
        until=until,
    )
    return MiddlewareStats(
        total_middleware=int(stats.get("total_middleware") or 0),
        total_invocations=int(stats.get("total_invocations") or 0),
        decisions=int(stats.get("decisions") or 0),
        allows=int(stats.get("allows") or 0),
        transforms=int(stats.get("transforms") or 0),
        blocks=int(stats.get("blocks") or 0),
        interruptions=int(stats.get("interruptions") or 0),
        sessions=int(stats.get("sessions") or 0),
    )


@router.get("/filters", response_model=MiddlewareFilterOptions)
async def get_middleware_filter_options(
    include_internal: bool = Query(False),
    q: EventQuery | None = Depends(get_query_or_none),
) -> MiddlewareFilterOptions:
    """Every value the ``/api/middleware`` filters can take, over the whole stream."""
    print_status(f"GET /api/middleware/filters include_internal={include_internal}")
    if q is None:
        return MiddlewareFilterOptions()
    return MiddlewareFilterOptions(
        **queries.list_middleware_filter_options(q.con, include_internal)
    )
