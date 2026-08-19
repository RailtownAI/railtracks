"""FastAPI routes for the visualizer, backed by the event-stream query layer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi import Path as PathParam

from railtracks.paths import resolve_railtracks_home

from ..io import print_error, print_status
from . import queries
from .models import (
    EventFilterOptions,
    EventPage,
    EventSortField,
    EventStats,
    GraphEdge,
    GraphNode,
    Guardrail,
    LLMTraceFilterOptions,
    LLMTracePage,
    LLMTraceSortField,
    LLMTraceStats,
    LLMTraceStatus,
    MiddlewareFilterOptions,
    MiddlewarePage,
    MiddlewareSortField,
    MiddlewareStats,
    NodeDetail,
    NodeRef,
    SessionDetail,
    SessionFilterOptions,
    SessionGraph,
    SessionStats,
    SessionSummary,
    SortOrder,
)
from .row_mapping import (
    _build_tree,
    _latency,
    _node_status,
    _row_to_event,
    _row_to_llm_trace,
    _row_to_middleware_summary,
    _row_to_session_middleware,
    _row_to_summary,
    _to_llm_content,
    _to_llm_contents,
    _tool_input_messages,
)

#: ``/api/v2``, not ``/api``. The v1 file-based endpoints in ``viz_server.py`` keep
#: the bare paths because the *released* visualizer build calls them and cannot be
#: changed — an ordinary ``railtracks viz`` with no staged UI downloads that build.
#: Everything here is beta and moves; putting the version in the prefix is what
#: lets the stable client keep working while this one changes underneath it.
router = APIRouter(prefix="/api/v2")

_EVENTS_SUBDIR = "data/new-ones"

#: UUID-shape pattern applied to ``{session_id}`` so the sibling literals
#: ``/sessions/stats`` and ``/sessions/filters`` are not swallowed as ids.
_SESSION_ID_PATTERN = (
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _events_dir() -> Path:
    return resolve_railtracks_home() / _EVENTS_SUBDIR


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/sessions", response_model=list[SessionSummary])
async def list_sessions(
    flow_name: list[str] | None = Query(None),
    entry_point_name: list[str] | None = Query(None),
    status: list[str] | None = Query(None),
    since: float | None = Query(None),
    until: float | None = Query(None),
) -> list[SessionSummary]:
    """List sessions in the events home, most recent first.

    Filters apply server-side. They used to run in the browser over the full
    list, which worked only because this endpoint returns every session — and
    could not produce honest stat tiles, since those must be computed over the
    same predicate rather than over whatever the client happened to hold.
    Repeating a param ORs its values; separate params AND.

    ``since`` / ``until`` are unix seconds bounding ``start_time`` — a session
    is in the window if it started in it. See :func:`queries._session_filters`.
    """
    print_status(
        f"GET /api/sessions flow_name={flow_name} "
        f"entry_point_name={entry_point_name} status={status} "
        f"since={since} until={until}"
    )
    events_dir = _events_dir()
    if not events_dir.exists():
        return []

    try:
        q = queries.get_query(events_dir)
        rows = queries.list_session_rows(
            q.con,
            flow_names=flow_name,
            entry_point_names=entry_point_name,
            statuses=status,
            since=since,
            until=until,
        )
        # Attached in one extra query keyed on the ids just returned, rather than
        # per row: a lookup inside the loop would be one query per session, and
        # re-deriving the session filter would give the middleware a second
        # predicate to drift from the rows it decorates.
        middleware = queries.list_middleware_by_session(
            q.con, [r["session_id"] for r in rows]
        )
    except Exception as e:  # noqa: BLE001 - keep the endpoint resilient
        print_error(f"list_sessions query failed: {e}")
        raise HTTPException(status_code=500, detail="failed to query events") from e

    return [
        _row_to_summary(
            r,
            [
                _row_to_session_middleware(m)
                for m in middleware.get(r["session_id"], [])
            ],
        )
        for r in rows
    ]


@router.get("/sessions/stats", response_model=SessionStats)
async def get_session_stats(
    flow_name: list[str] | None = Query(None),
    entry_point_name: list[str] | None = Query(None),
    status: list[str] | None = Query(None),
    since: float | None = Query(None),
    until: float | None = Query(None),
) -> SessionStats:
    """Roll-up across every session matching the filters.

    Takes the same filter params as ``/api/sessions`` — tiles that narrowed
    differently from the table beneath them would be worse than no tiles.
    """
    print_status(
        f"GET /api/sessions/stats flow_name={flow_name} "
        f"entry_point_name={entry_point_name} status={status} "
        f"since={since} until={until}"
    )
    events_dir = _events_dir()
    if not events_dir.exists():
        return SessionStats()

    q = queries.get_query(events_dir)
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
        running=int(stats.get("running") or 0),
        input_tokens=int(stats.get("input_tokens") or 0),
        output_tokens=int(stats.get("output_tokens") or 0),
        total_cost=float(stats.get("total_cost") or 0.0),
    )


@router.get("/sessions/filters", response_model=SessionFilterOptions)
async def get_session_filter_options() -> SessionFilterOptions:
    """Values the session filters accept, across every session in the stream."""
    print_status("GET /api/sessions/filters")
    events_dir = _events_dir()
    if not events_dir.exists():
        return SessionFilterOptions()

    q = queries.get_query(events_dir)
    return SessionFilterOptions(**queries.list_session_filter_options(q.con))


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: str = PathParam(..., pattern=_SESSION_ID_PATTERN),
) -> SessionDetail:
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
async def get_node_detail(
    session_id: str = PathParam(..., pattern=_SESSION_ID_PATTERN),
    node_id: str = PathParam(...),
) -> NodeDetail:
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


@router.get("/llm-traces", response_model=LLMTracePage)
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

    One row per round trip, whether it returned or raised — see
    :class:`LLMTrace`. ``status`` narrows to one outcome, which is what makes
    three errors among four hundred calls findable at all: they cannot be
    sorted to the top (an error has no cost, tokens or latency to rank on) and
    scrolling for them is not a plan.

    Filters (``flow_name``, ``node_name``, ``model_name``, ``status``,
    ``session_id``, ``node_id``, and the ``since`` / ``until`` window over the
    call's own timestamp) and sorting (``sort_by`` / ``order``) both
    apply server-side, before paging. Repeating ``flow_name`` / ``node_name`` /
    ``model_name`` / ``status`` ORs the values within that filter and ANDs
    across filters. An offset past the end returns no rows, not an error.

    Sorting the page in the browser would be a different question: "the ten
    priciest calls" is not "the priciest of the fifty most recent". See
    :func:`queries.list_llm_trace_rows`.

    Returns a :class:`LLMTracePage`, so ``total`` reflects every matching row and a
    client can size its pager without over-fetching to probe for a next page.
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


@router.get("/llm-traces/stats", response_model=LLMTraceStats)
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
    """Roll-up across every LLM call matching the filters.

    Takes the same filters as ``/api/llm-traces`` — ``status`` and the
    ``since`` / ``until`` window included, so the tiles keep describing the rows
    underneath them once the reader narrows — and no paging params: the point of the tiles is to describe the
    whole filtered set, which is exactly what the fifty rows on the current page
    cannot tell you.
    """
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


@router.get("/llm-traces/filters", response_model=LLMTraceFilterOptions)
async def get_llm_trace_filter_options() -> LLMTraceFilterOptions:
    """Every value the ``/api/llm-traces`` filters can take.

    A dropdown built from the rows on the current page can only ever offer what
    the current filter already matched, which makes the filters unable to widen
    a selection. These lists come from the whole stream instead.
    """
    print_status("GET /api/llm-traces/filters")
    events_dir = _events_dir()
    if not events_dir.exists():
        return LLMTraceFilterOptions()

    q = queries.get_query(events_dir)
    options = queries.list_llm_trace_filter_options(q.con)
    return LLMTraceFilterOptions(**options)


@router.get("/events", response_model=EventPage)
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
) -> EventPage:
    """List raw events from the stream, newest first by default.

    One row per event — see :class:`StreamEvent` for why this is a different
    grain from ``/api/llm-traces`` rather than the same rows under a filter.
    This reads the ``events`` view, so it shows every namespace in the stream,
    including one the registry does not declare.

    Filters (``namespace``, ``event_type``, ``flow_name``, ``middleware_name``,
    ``session_id``, ``node_id``, ``failures_only``, a ``search`` substring, and
    the ``since`` / ``until`` window over the event's own stamp) and sorting
    (``sort_by`` / ``order``) both apply server-side, before paging. Repeating
    ``namespace`` / ``event_type`` / ``flow_name`` / ``middleware_name`` ORs the
    values within that filter and ANDs across filters. An offset past the end
    returns no rows, not an error.

    ``search`` is a substring test over the event type, session id, flow name,
    node name and the payload text — not a ``LIKE`` pattern, so ``%`` and ``_``
    are searched for literally.

    ``middleware_name`` is an exact match, and it is a filter of its own rather
    than a ``search`` because a middleware's name appears in exactly one of its
    events: ``middleware.creation`` records it, and every invocation, response,
    failure and guard decision identifies its middleware by type id. Searching a
    name therefore returns the creations and none of the work — 81 rows for a
    middleware that ran 79 times, on the store this was measured against. The
    server resolves the id to the name instead (see
    :data:`~railtracks.cli.viz_api.queries._MIDDLEWARE_NAME_CTE`), which is what
    lets the Middleware view hand off to the log.
    """
    print_status(
        f"GET /api/events limit={limit} offset={offset} "
        f"session_id={session_id} node_id={node_id} "
        f"namespace={namespace} event_type={event_type} flow_name={flow_name} "
        f"middleware_name={middleware_name} "
        f"failures_only={failures_only} search={search!r} "
        f"since={since} until={until} "
        f"sort_by={sort_by.value} order={order.value}"
    )
    events_dir = _events_dir()
    if not events_dir.exists():
        return EventPage(rows=[], total=0, limit=limit, offset=offset)

    q = queries.get_query(events_dir)
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


@router.get("/events/stats", response_model=EventStats)
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
) -> EventStats:
    """Roll-up across every event matching the filters.

    Takes the same filters as ``/api/events`` and no paging params: the tiles
    describe the whole filtered set, which is what the rows on the current page
    cannot report.
    """
    print_status(
        f"GET /api/events/stats session_id={session_id} node_id={node_id} "
        f"namespace={namespace} event_type={event_type} flow_name={flow_name} "
        f"middleware_name={middleware_name} "
        f"failures_only={failures_only} search={search!r} "
        f"since={since} until={until}"
    )
    events_dir = _events_dir()
    if not events_dir.exists():
        return EventStats()

    q = queries.get_query(events_dir)
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


@router.get("/events/filters", response_model=EventFilterOptions)
async def get_event_filter_options() -> EventFilterOptions:
    """Every value the ``/api/events`` filters can take, over the whole stream.

    Options built from the loaded rows could only ever offer what the active
    filter already matched, which leaves no way to widen a selection.
    """
    print_status("GET /api/events/filters")
    events_dir = _events_dir()
    if not events_dir.exists():
        return EventFilterOptions()

    q = queries.get_query(events_dir)
    return EventFilterOptions(**queries.list_event_filter_options(q.con))


@router.get("/middleware", response_model=MiddlewarePage)
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
) -> MiddlewarePage:
    """List middleware, one row per ``(name, kind, band)``, busiest first.

    An aggregate rather than one row per invocation — see
    :class:`MiddlewareSummary` for why the set is the row. The per-invocation
    stream is ``/api/events?namespace=middleware``, at event grain.

    ``kind`` is derived rather than served by the framework: it comes from which
    specialised event types a middleware emits, as a precedence ladder. See
    :data:`queries._MIDDLEWARE_KIND_CASE`.

    Filters and sorting apply server-side, before paging. Repeating ``kind`` /
    ``band`` / ``middleware_name`` / ``flow_name`` ORs the values within that
    filter and ANDs across filters.

    ``include_internal`` surfaces the framework's own ``_observe_middleware`` and
    ``_llm_observe``, which are hidden by default: they are injected on every node
    and every model chain, so they appear in every session and say nothing about
    the code under observation. They are worth being able to see, which is why
    this is a flag rather than a permanent exclusion.

    ``blocks_only`` narrows to middleware that blocked at least once. It is a
    ``HAVING`` over the group rather than a row predicate, so a guard that blocked
    once in forty runs keeps all forty invocations in its totals.
    """
    print_status(
        f"GET /api/middleware limit={limit} offset={offset} "
        f"session_id={session_id} node_id={node_id} kind={kind} band={band} "
        f"middleware_name={middleware_name} flow_name={flow_name} "
        f"blocks_only={blocks_only} include_internal={include_internal} "
        f"since={since} until={until} "
        f"sort_by={sort_by.value} order={order.value}"
    )
    events_dir = _events_dir()
    if not events_dir.exists():
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
    q = queries.get_query(events_dir)
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


@router.get("/middleware/stats", response_model=MiddlewareStats)
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
) -> MiddlewareStats:
    """Roll-up across every middleware matching the filters.

    Takes the same filters as ``/api/middleware`` and no paging params, and shares
    its ``WHERE`` and ``HAVING`` — so a tile can never describe a set the table
    cannot list.
    """
    print_status(
        f"GET /api/middleware/stats session_id={session_id} node_id={node_id} "
        f"kind={kind} band={band} middleware_name={middleware_name} "
        f"flow_name={flow_name} blocks_only={blocks_only} "
        f"include_internal={include_internal} since={since} until={until}"
    )
    events_dir = _events_dir()
    if not events_dir.exists():
        return MiddlewareStats()

    q = queries.get_query(events_dir)
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


@router.get("/middleware/filters", response_model=MiddlewareFilterOptions)
async def get_middleware_filter_options(
    include_internal: bool = Query(False),
) -> MiddlewareFilterOptions:
    """Every value the ``/api/middleware`` filters can take, over the whole stream.

    Options built from the loaded rows could only ever offer what the active
    filter already matched, which leaves no way to widen a selection.
    ``include_internal`` is threaded through so the dropdown cannot offer a name
    the default listing would refuse to show.
    """
    print_status(f"GET /api/middleware/filters include_internal={include_internal}")
    events_dir = _events_dir()
    if not events_dir.exists():
        return MiddlewareFilterOptions()

    q = queries.get_query(events_dir)
    return MiddlewareFilterOptions(
        **queries.list_middleware_filter_options(q.con, include_internal)
    )


@router.get("/sessions/{session_id}/graph", response_model=SessionGraph)
async def get_session_graph(
    session_id: str = PathParam(..., pattern=_SESSION_ID_PATTERN),
) -> SessionGraph:
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
