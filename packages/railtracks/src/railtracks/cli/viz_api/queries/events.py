"""Events — the raw stream, one row per event.

This is the one endpoint that reads the ``events`` view rather than a
namespace view, and that is the point of it: ``events`` is the raw envelope
plus the untyped ``payload``, so it carries *every* event in the stream —
including one whose namespace the registry does not declare yet. A log built
on the namespace views could only ever show the four registered namespaces,
which makes it useless for the job a log exists to do: seeing the event you
just added and have not registered.

It also means the time column is the envelope's ``stamp`` rather than the
payload's ``timestamp``. ``stamp`` is on every event unconditionally, where
``timestamp`` is a registry-declared payload key and would be null for an
unregistered namespace.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..models import EventSortField, SortOrder
from ._common import (
    _MIDDLEWARE_NAME_CTE,
    _NODE_JOIN_CTE,
    _SESSION_JOIN_CTE,
    _in_clause,
    _order_clause,
    _parse_json,
    _rows,
    _window_predicates,
)

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection


#: SQL for each sortable measure, in terms of the ``ev`` alias ``e``. Keyed by
#: the enum, so nothing user-supplied reaches the ``ORDER BY``.
_EVENT_SORT_COLUMNS = {
    EventSortField.TIMESTAMP: "e.stamp",
    EventSortField.EVENT_TYPE: "e.event_type",
    EventSortField.PAYLOAD_BYTES: "e.payload_bytes",
}

#: The denormalizing CTEs for the events listing — shared with the LLM traces
#: listing, and grouped by their join key for the same reason.
_EVENT_JOIN_CTES = ",".join([_SESSION_JOIN_CTE, _NODE_JOIN_CTE])

#: The joins that pair with :data:`_EVENT_JOIN_CTES`, binding the aliases the
#: predicates in :func:`_event_filters` are written against.
_EVENT_JOINS = """
    LEFT JOIN sessions s
      ON s.scope_id = e.session_id
    LEFT JOIN nodes n
      ON n.scope_id = e.session_id AND n.node_id = e.node_id
"""

#: The text a search matches against. The payload is the bulk of it, but a
#: reader hunting an agent by name needs the joined columns too — an
#: ``llm.response`` payload never mentions the node it was made from.
#: ``CONCAT_WS`` skips nulls, where ``||`` would make the whole expression null
#: and silently drop the row from every search.
_EVENT_SEARCH_TEXT = (
    "CONCAT_WS(' ', e.event_type, e.session_id, s.flow_name, n.node_name, "
    "e.payload_text)"
)


def _event_rows_cte() -> str:
    """The rows the event endpoints are built from: one per event in the stream.

    Everything derived lives here so the listing, the count and the stats read
    one definition of it:

    * ``namespace`` is the event type's first segment, which is what the
      registry itself keys namespaces by.
    * ``node_id`` resolves the node an event *belongs to*, from a direct key
      where the event has one and through the LLM invocation where it does not.

      The direct COALESCE order is load-bearing. ``node.creation`` carries its
      own id under ``node_id``; the other ``node.*`` events carry theirs under
      ``parent_node_id`` while *also* carrying their tree parent under
      ``spatial_parent_node_id``; ``llm.*`` carries only the node it happened
      inside, under ``spatial_parent_node_id``. Reading the spatial key before
      the parent key therefore attributes several hundred ``node.*`` events to
      their parent instead of themselves — measured at 351 of them on a
      3,887-event stream.

      ``middleware.*`` events carry no node key at all. They name the LLM
      invocation they wrapped, under ``spatial_parent_llm_invoke_id``, and the
      LLM events for that invocation name the node — so one hop recovers them,
      the same hop :func:`list_guardrails_by_node` makes to attribute a
      guardrail decision. It is worth making: on the same stream it moves 900
      events out of "no node", a little under a quarter of the whole log.

      What is left genuinely has no node, and the client says so rather than
      guessing: ``session.started`` / ``session.completed`` belong to the
      session, and ``llm.creation`` / ``middleware.creation`` create a *type*
      (keyed by ``llm_id`` / ``middleware_type_id``) outside any node
      invocation. 926 events on this stream, and correctly unattributed.
    * ``middleware_name``, for the middleware events, resolved through
      :data:`_MIDDLEWARE_NAME_CTE`. It exists so the Middleware view can hand off
      to the log — "every event this middleware produced" is not something a text
      search can express, because only ``middleware.creation`` carries the name.
      Null for every non-middleware event, which is what a name filter then
      excludes.
    * ``is_failure`` is the ``.failure`` suffix the event namespaces use for a
      raised exception (``llm.failure``, ``node.failure``,
      ``middleware.failure``). It is derived once here so the Failures tile, the
      failures filter and the row marker cannot disagree about what counts.
      Note this is an *event* that reported an exception, not a session's
      rolled-up status — ``session.completed`` carries that under ``status``.
    * ``payload_bytes`` is the serialized payload's size, in bytes rather than
      characters. Served rather than measured in the browser because the column
      is sortable, and a sort has to run server-side before paging; a client
      that recomputed it could show a figure the ordering did not use.

    ``payload_text`` is the serialized payload, projected once and used three
    ways: the listing returns it for the client to parse, ``payload_bytes``
    measures it, and the search predicate matches against it. All three queries
    carry it, because all three share one ``WHERE`` clause and that clause can
    search the payload — a variant that omitted the column would raise a binder
    error the moment a search was passed to it. Carrying it is free where it is
    unused: DuckDB prunes an unreferenced projection out of an inlined CTE.
    """
    return (
        _MIDDLEWARE_NAME_CTE
        + ","
        + """
    llm_nodes AS (
      -- The node each LLM invocation was made from, so a middleware event that
      -- names only the invocation can still find its node. Grouped by the join
      -- key like every other join here: an ungrouped match would fan one event
      -- row out into as many nodes as it hit.
      SELECT scope_id,
             parent_llm_invoke_id              AS llm_invoke_id,
             ANY_VALUE(spatial_parent_node_id) AS node_id
      FROM llm
      WHERE event_type IN ('llm.invocation', 'llm.response', 'llm.failure')
        AND parent_llm_invoke_id IS NOT NULL
        AND spatial_parent_node_id IS NOT NULL
      GROUP BY scope_id, parent_llm_invoke_id
    ),
    ev_raw AS (
      SELECT event_id,
             event_type,
             SPLIT_PART(event_type, '.', 1)                  AS namespace,
             scope_id                                        AS session_id,
             scope_type,
             parent_scope_id,
             stamp,
             COALESCE(payload->>'node_id',
                      payload->>'parent_node_id',
                      payload->>'spatial_parent_node_id')    AS direct_node_id,
             payload->>'spatial_parent_llm_invoke_id'        AS llm_invoke_id,
             -- Its own id on a creation, the wrapped middleware's on everything
             -- else. Both, so a name filter keeps the creation that named it.
             COALESCE(payload->>'middleware_type_id',
                      payload->>'parent_middleware_type_id') AS mw_type_id,
             event_type LIKE '%.failure'                     AS is_failure,
             CAST(payload AS VARCHAR)                        AS payload_text,
             STRLEN(payload_text)                            AS payload_bytes
      FROM events
    ),
    ev AS (
      SELECT r.event_id,
             r.event_type,
             r.namespace,
             r.session_id,
             r.scope_type,
             r.parent_scope_id,
             r.stamp,
             -- A direct key always wins; the hop only fills a gap.
             COALESCE(r.direct_node_id, ln.node_id)          AS node_id,
             nm.middleware_name,
             r.is_failure,
             r.payload_text,
             r.payload_bytes
      FROM ev_raw r
      LEFT JOIN llm_nodes ln
        ON ln.scope_id = r.session_id AND ln.llm_invoke_id = r.llm_invoke_id
      LEFT JOIN mw_names nm
        ON nm.type_id = r.mw_type_id
    )"""
    )


def _event_filters(
    session_id: str | None,
    node_id: str | None,
    namespaces: list[str] | None,
    event_types: list[str] | None,
    flow_names: list[str] | None,
    middleware_names: list[str] | None = None,
    failures_only: bool = False,
    search: str | None = None,
    since: float | None = None,
    until: float | None = None,
) -> tuple[str, list[Any]]:
    """Build the ``WHERE`` clause shared by the event listing, count and stats.

    All three go through here so the tiles, the pager total and the rows can
    never describe three different sets. That means all three must expose the
    same aliases — ``e`` for the event rows, ``s`` for the session, ``n`` for
    the node.

    ``search`` is a plain substring test, not a ``LIKE`` pattern: ``contains``
    has no wildcard characters, so a reader typing ``_`` or ``%`` searches for
    that character instead of accidentally matching everything.

    ``middleware_names`` is an exact match on the resolved name rather than a
    search for it, which is the whole point: the name lives only on
    ``middleware.creation``, so a text search for one returns that middleware's
    creations and none of its work.

    ``since`` / ``until`` bound the envelope's own ``stamp`` — an event is in
    the window if it *happened* in it, regardless of when the session around it
    started.
    """
    predicates: list[str] = []
    params: list[Any] = []
    if session_id:
        predicates.append("e.session_id = ?")
        params.append(session_id)
    if node_id:
        predicates.append("e.node_id = ?")
        params.append(node_id)
    if namespaces:
        predicates.append(_in_clause("e.namespace", namespaces))
        params.extend(namespaces)
    if event_types:
        predicates.append(_in_clause("e.event_type", event_types))
        params.extend(event_types)
    if flow_names:
        predicates.append(_in_clause("s.flow_name", flow_names))
        params.extend(flow_names)
    if middleware_names:
        predicates.append(_in_clause("e.middleware_name", middleware_names))
        params.extend(middleware_names)
    if failures_only:
        predicates.append("e.is_failure")
    if search:
        predicates.append(f"CONTAINS(LOWER({_EVENT_SEARCH_TEXT}), LOWER(?))")
        params.append(search)
    window, window_params = _window_predicates("EPOCH(e.stamp)", since, until)
    predicates.extend(window)
    params.extend(window_params)

    return ("WHERE " + " AND ".join(predicates) if predicates else "", params)


def _event_order_clause(sort_by: EventSortField, order: SortOrder) -> str:
    """``ORDER BY`` for the event listing. See :func:`_order_clause`.

    ``event_id`` is the unique final tiebreaker, and newest-first is the
    secondary key for the two non-chronological measures — grouping the log by
    event type is only readable if each group is itself in time order.
    """
    tiebreakers = [] if sort_by is EventSortField.TIMESTAMP else ["e.stamp DESC"]
    return _order_clause(
        _EVENT_SORT_COLUMNS[sort_by],
        order,
        [*tiebreakers, "e.event_id ASC"],
    )


def count_event_rows(
    con: DuckDBPyConnection,
    *,
    session_id: str | None = None,
    node_id: str | None = None,
    namespaces: list[str] | None = None,
    event_types: list[str] | None = None,
    flow_names: list[str] | None = None,
    middleware_names: list[str] | None = None,
    failures_only: bool = False,
    search: str | None = None,
    since: float | None = None,
    until: float | None = None,
) -> int:
    """Count events matching the filters, ignoring paging.

    Selects no payload column — it is the expensive part of
    :func:`list_event_rows` and a count needs none of it.
    """
    where_clause, params = _event_filters(
        session_id,
        node_id,
        namespaces,
        event_types,
        flow_names,
        middleware_names,
        failures_only,
        search,
        since,
        until,
    )
    sql = f"""
    WITH {_event_rows_cte()},
    {_EVENT_JOIN_CTES}
    SELECT COUNT(*) AS total
    FROM ev e
    {_EVENT_JOINS}
    {where_clause}
    """
    rows = _rows(con, sql, tuple(params), label="count_event_rows")
    return int(rows[0]["total"]) if rows else 0


def list_event_rows(
    con: DuckDBPyConnection,
    *,
    limit: int,
    offset: int,
    session_id: str | None = None,
    node_id: str | None = None,
    namespaces: list[str] | None = None,
    event_types: list[str] | None = None,
    flow_names: list[str] | None = None,
    middleware_names: list[str] | None = None,
    failures_only: bool = False,
    search: str | None = None,
    since: float | None = None,
    until: float | None = None,
    sort_by: EventSortField = EventSortField.TIMESTAMP,
    order: SortOrder = SortOrder.DESC,
) -> list[dict[str, Any]]:
    """Return event rows with server-side filtering, sorting and paging.

    Denormalizes ``flow_name`` / ``flow_id`` from the session and ``node_name``
    from the node onto every row, so the log can be read and deep-linked
    without a second lookup.

    The payload comes back whole, as the ``dict`` it was written as. The reader
    opens one row at a time, so the alternative — a separate fetch per row —
    would buy a smaller page at the cost of a round trip on every click; a page
    of 50 measures ~40–125 KiB on a representative stream.
    """
    where_clause, params = _event_filters(
        session_id,
        node_id,
        namespaces,
        event_types,
        flow_names,
        middleware_names,
        failures_only,
        search,
        since,
        until,
    )
    order_clause = _event_order_clause(sort_by, order)

    sql = f"""
    WITH {_event_rows_cte()},
    {_EVENT_JOIN_CTES}
    SELECT
      e.event_id,
      e.event_type,
      e.namespace,
      e.session_id,
      e.scope_type,
      e.parent_scope_id,
      EPOCH(e.stamp)                    AS timestamp,
      s.flow_id,
      s.flow_name,
      e.node_id,
      n.node_name,
      e.middleware_name,
      e.is_failure,
      e.payload_bytes,
      e.payload_text                     AS payload_json
    FROM ev e
    {_EVENT_JOINS}
    {where_clause}
    {order_clause}
    LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])
    rows = _rows(
        con,
        sql,
        tuple(params),
        label=f"list_event_rows(limit={limit}, offset={offset}, sort={sort_by.value}:{order.value})",
    )
    for row in rows:
        row["payload"] = _parse_json(row.pop("payload_json"))
    return rows


def get_event_stats(
    con: DuckDBPyConnection,
    *,
    session_id: str | None = None,
    node_id: str | None = None,
    namespaces: list[str] | None = None,
    event_types: list[str] | None = None,
    flow_names: list[str] | None = None,
    middleware_names: list[str] | None = None,
    failures_only: bool = False,
    search: str | None = None,
    since: float | None = None,
    until: float | None = None,
) -> dict[str, Any]:
    """Roll-up across every event matching the filters, ignoring paging.

    Shares ``_event_filters`` and ``_event_rows_cte`` with the listing and its
    count, so a tile can never count a set the table cannot list.
    """
    where_clause, params = _event_filters(
        session_id,
        node_id,
        namespaces,
        event_types,
        flow_names,
        middleware_names,
        failures_only,
        search,
        since,
        until,
    )
    sql = f"""
    WITH {_event_rows_cte()},
    {_EVENT_JOIN_CTES}
    SELECT COUNT(*)                             AS total_events,
           COUNT(*) FILTER (WHERE e.is_failure) AS failures,
           COUNT(DISTINCT e.session_id)         AS sessions,
           COUNT(DISTINCT e.event_type)         AS event_types,
           MIN(EPOCH(e.stamp))                  AS first_timestamp,
           MAX(EPOCH(e.stamp))                  AS last_timestamp
    FROM ev e
    {_EVENT_JOINS}
    {where_clause}
    """
    rows = _rows(con, sql, tuple(params), label="get_event_stats")
    return rows[0] if rows else {}


def list_event_filter_options(con: DuckDBPyConnection) -> dict[str, list[str]]:
    """Distinct namespaces, event types and flow names across the whole stream.

    Computed over every event rather than the current page, like the other
    filter-option endpoints: options drawn from the rows in hand could only ever
    offer what the active filter already matched, leaving no way to widen a
    selection.

    ``event_types`` is returned flat and sorted, which groups it by namespace
    for free — the namespace is the type's own first segment.

    There is no ``statuses`` list. An event either reported an exception or did
    not, which is the two-valued ``failures_only`` flag the contract already
    names rather than something to discover from the data.
    """
    type_rows = _rows(
        con,
        """
        SELECT DISTINCT event_type, SPLIT_PART(event_type, '.', 1) AS namespace
        FROM events
        WHERE event_type IS NOT NULL AND event_type <> ''
        ORDER BY event_type
        """,
        label="event_filter_options.event_types",
    )

    flow_rows = _rows(
        con,
        """
        SELECT DISTINCT flow_name
        FROM session
        WHERE event_type = 'session.started'
          AND flow_name IS NOT NULL
          AND flow_name <> ''
        ORDER BY flow_name
        """,
        label="event_filter_options.flow_names",
    )

    return {
        "namespaces": sorted({r["namespace"] for r in type_rows if r["namespace"]}),
        "event_types": [r["event_type"] for r in type_rows],
        "flow_names": [r["flow_name"] for r in flow_rows],
    }
