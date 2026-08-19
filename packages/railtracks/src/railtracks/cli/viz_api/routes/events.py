"""Raw event log — one row per event in the stream."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from railtracks.query import EventQuery

from .. import queries
from .._debug import debug_print
from ..models import (
    EventFilterOptions,
    EventPage,
    EventSortField,
    EventStats,
    SortOrder,
)
from ..row_mapping import _row_to_event
from ._common import QueryFailureRoute, get_query_or_none

router = APIRouter(prefix="/events", tags=["events"], route_class=QueryFailureRoute)


@router.get("", response_model=EventPage)
async def list_events(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session_id: str | None = Query(None),
    node_id: str | None = Query(None),
    namespace: list[str] | None = Query(None),
    event_type: list[str] | None = Query(None),
    flow_name: list[str] | None = Query(None),
    middleware_name: list[str] | None = Query(None),
    failures_only: bool = Query(False),
    search: str | None = Query(None),
    since: float | None = Query(None),
    until: float | None = Query(None),
    sort_by: EventSortField = Query(EventSortField.TIMESTAMP),
    order: SortOrder = Query(SortOrder.DESC),
    q: EventQuery | None = Depends(get_query_or_none),
) -> EventPage:
    """List raw events from the stream, newest first by default.

    Reads the ``events`` view, so every namespace shows — including one the
    registry does not declare. Filters and sort apply server-side, before
    paging. ``search`` is a substring test (not a ``LIKE`` pattern);
    ``middleware_name`` is exact match on the resolved name.
    """
    debug_print(
        f"GET /api/v2/events limit={limit} offset={offset} "
        f"session_id={session_id} node_id={node_id} "
        f"namespace={namespace} event_type={event_type} flow_name={flow_name} "
        f"middleware_name={middleware_name} "
        f"failures_only={failures_only} search={search!r} "
        f"since={since} until={until} "
        f"sort_by={sort_by.value} order={order.value}"
    )
    if q is None:
        return EventPage(rows=[], total=0, limit=limit, offset=offset)

    rows = queries.list_event_rows(
        q.con,
        limit=limit,
        offset=offset,
        session_id=session_id,
        node_id=node_id,
        namespaces=namespace,
        event_types=event_type,
        flow_names=flow_name,
        middleware_names=middleware_name,
        failures_only=failures_only,
        search=search,
        since=since,
        until=until,
        sort_by=sort_by,
        order=order,
    )
    total = queries.count_event_rows(
        q.con,
        session_id=session_id,
        node_id=node_id,
        namespaces=namespace,
        event_types=event_type,
        flow_names=flow_name,
        middleware_names=middleware_name,
        failures_only=failures_only,
        search=search,
        since=since,
        until=until,
    )
    return EventPage(
        rows=[_row_to_event(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/stats", response_model=EventStats)
async def get_event_stats(
    session_id: str | None = Query(None),
    node_id: str | None = Query(None),
    namespace: list[str] | None = Query(None),
    event_type: list[str] | None = Query(None),
    flow_name: list[str] | None = Query(None),
    middleware_name: list[str] | None = Query(None),
    failures_only: bool = Query(False),
    search: str | None = Query(None),
    since: float | None = Query(None),
    until: float | None = Query(None),
    q: EventQuery | None = Depends(get_query_or_none),
) -> EventStats:
    """Roll-up across every event matching the filters, ignoring paging."""
    debug_print(
        f"GET /api/v2/events/stats session_id={session_id} node_id={node_id} "
        f"namespace={namespace} event_type={event_type} flow_name={flow_name} "
        f"middleware_name={middleware_name} "
        f"failures_only={failures_only} search={search!r} "
        f"since={since} until={until}"
    )
    if q is None:
        return EventStats()

    stats = queries.get_event_stats(
        q.con,
        session_id=session_id,
        node_id=node_id,
        namespaces=namespace,
        event_types=event_type,
        flow_names=flow_name,
        middleware_names=middleware_name,
        failures_only=failures_only,
        search=search,
        since=since,
        until=until,
    )
    first = stats.get("first_timestamp")
    last = stats.get("last_timestamp")
    return EventStats(
        total_events=int(stats.get("total_events") or 0),
        failures=int(stats.get("failures") or 0),
        sessions=int(stats.get("sessions") or 0),
        event_types=int(stats.get("event_types") or 0),
        first_timestamp=float(first) if first is not None else None,
        last_timestamp=float(last) if last is not None else None,
    )


@router.get("/filters", response_model=EventFilterOptions)
async def get_event_filter_options(
    q: EventQuery | None = Depends(get_query_or_none),
) -> EventFilterOptions:
    """Every value the ``/api/events`` filters can take, over the whole stream."""
    debug_print("GET /api/v2/events/filters")
    if q is None:
        return EventFilterOptions()
    return EventFilterOptions(**queries.list_event_filter_options(q.con))
