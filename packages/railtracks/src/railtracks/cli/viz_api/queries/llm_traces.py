"""LLM traces — one row per round trip, denormalized with session & node.

The listing, count and stats all read the same ``llm_calls`` CTE through the
same ``WHERE`` builder, so a row can't be listed without being counted, or
counted without being listed. ``llm.failure`` is unioned into the CTE
alongside ``llm.response`` so a call that raised is still surfaced — with
zero tokens, zero cost and null latency, matching what the provider reported.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..models import LLMTraceSortField, LLMTraceStatus, SortOrder
from ._common import (
    _LLM_CREATION_JOIN_CTE,
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


#: SQL for each sortable measure, in terms of the ``llm_calls`` alias ``r``.
#: Lookups are keyed by :class:`LLMTraceSortField`, so nothing user-supplied ever
#: reaches the ``ORDER BY`` — the enum is validated at the route boundary and a
#: miss here would raise, not interpolate.
_LLM_TRACE_SORT_COLUMNS = {
    LLMTraceSortField.TIMESTAMP: "r.timestamp",
    LLMTraceSortField.COST: "COALESCE(r.total_cost, 0.0)",
    LLMTraceSortField.TOKENS: "COALESCE(r.input_tokens, 0) + COALESCE(r.output_tokens, 0)",
    LLMTraceSortField.LATENCY: "r.latency",
}

#: Quoted SQL literals for the two ``LLMTraceStatus`` values, derived once so
#: renaming the enum value keeps the CASE branches and the failed-call filter
#: in step.
_STATUS_ERROR_LITERAL = f"'{LLMTraceStatus.ERROR.value}'"
_STATUS_SUCCESS_LITERAL = f"'{LLMTraceStatus.SUCCESS.value}'"


def _llm_trace_filters(
    session_id: str | None,
    node_id: str | None,
    flow_names: list[str] | None,
    node_names: list[str] | None,
    model_names: list[str] | None,
    statuses: list[LLMTraceStatus] | None = None,
    since: float | None = None,
    until: float | None = None,
) -> tuple[str, list[Any]]:
    """Build the shared ``WHERE`` clause for the trace queries.

    Both :func:`list_llm_trace_rows` and :func:`count_llm_trace_rows` go through here so
    a page and its total can never be computed over different predicates. That
    also means both queries must expose the same aliases — ``r`` for the LLM
    calls, ``s`` for the session, ``cr`` for the LLM creation and ``n`` for the
    node.

    ``since`` / ``until`` are unix seconds, inclusive and exclusive
    respectively, and bound the call's own timestamp — a call is in the window
    if it was *made* in it, regardless of when the session around it started.
    ``r.timestamp`` is a SQL ``TIMESTAMP``, so the comparison goes through
    ``EPOCH()`` rather than casting the parameter; the ordering clause still
    sorts on the raw column.
    """
    predicates: list[str] = []
    params: list[Any] = []
    if session_id:
        predicates.append("r.scope_id = ?")
        params.append(session_id)
    if node_id:
        predicates.append("r.spatial_parent_node_id = ?")
        params.append(node_id)
    if flow_names:
        predicates.append(_in_clause("s.flow_name", flow_names))
        params.extend(flow_names)
    if node_names:
        predicates.append(_in_clause("n.node_name", node_names))
        params.extend(node_names)
    if model_names:
        predicates.append(
            _in_clause("COALESCE(r.reported_model_name, cr.model_name)", model_names)
        )
        params.extend(model_names)
    if statuses:
        predicates.append(_in_clause("r.status", statuses))
        # ``status`` is derived inside ``_llm_calls_cte``, so the values compared
        # against it are that CASE's own strings, not the event types.
        params.extend(s.value for s in statuses)
    window, window_params = _window_predicates("EPOCH(r.timestamp)", since, until)
    predicates.extend(window)
    params.extend(window_params)

    return ("WHERE " + " AND ".join(predicates) if predicates else "", params)


def _llm_trace_order_clause(sort_by: LLMTraceSortField, order: SortOrder) -> str:
    """``ORDER BY`` for the LLM trace listing. See :func:`_order_clause` for the
    NULLS-LAST and unique-tiebreaker rules this shares with the other listings.

    Newest-first is the secondary key for every measure except time itself, so
    equal-cost calls read chronologically rather than arbitrarily.
    """
    tiebreakers = [] if sort_by is LLMTraceSortField.TIMESTAMP else ["r.timestamp DESC"]
    return _order_clause(
        _LLM_TRACE_SORT_COLUMNS[sort_by],
        order,
        [*tiebreakers, "r.event_id ASC"],
    )


def _llm_calls_cte(*, with_payload: bool) -> str:
    """The rows the trace endpoints are built from: one per LLM round trip,
    whether it returned or raised.

    ``llm.failure`` carries the message history it was sent, the node and LLM it
    belongs to, and the exception — but none of the response columns, which the
    view leaves null. That is exactly the shape we want downstream: tokens and
    cost ``COALESCE`` to zero (nothing was reported, and nothing is billed for a
    call that never came back), and latency stays null so an error sorts last in
    both directions rather than reading as the fastest call in the run.

    All three trace queries build on this one CTE so a row can't be listed
    without being counted, or counted without being listed. The payload columns
    are opt-in: the JSON blobs are the expensive part of a listing, and neither
    the count nor the stats touch them.
    """
    payload = (
        """,
             message_input,
             output"""
        if with_payload
        else ""
    )
    return f"""
    llm_calls AS (
      SELECT event_id,
             scope_id,
             spatial_parent_node_id,
             timestamp,
             parent_llm_type_id,
             reported_model_name,
             input_tokens,
             output_tokens,
             total_cost,
             latency,
             exception_name,
             exception_message,
             CASE WHEN event_type = 'llm.failure'
                  THEN {_STATUS_ERROR_LITERAL}
                  ELSE {_STATUS_SUCCESS_LITERAL}
             END AS status{payload}
      FROM llm
      WHERE event_type IN ('llm.response', 'llm.failure')
    ),"""


#: The denormalizing CTEs shared by the LLM trace listing and its count.
#:
#: Every one of them is grouped by its join key. The stream can carry a repeated
#: ``llm.creation``, ``session.started`` or ``node.creation`` for the same
#: entity, and an ungrouped join then fans a single LLM response out into as
#: many rows as it matched — the bug that once had ``/api/llm-traces`` reporting
#: 44 rows for a 30-call stream. Add a join here and group it the same way.
_LLM_TRACE_JOIN_CTES = ",".join(
    [_LLM_CREATION_JOIN_CTE, _SESSION_JOIN_CTE, _NODE_JOIN_CTE]
)

#: The joins that pair with :data:`_LLM_TRACE_JOIN_CTES`, binding the aliases the
#: filter predicates in :func:`_llm_trace_filters` are written against.
_LLM_TRACE_JOINS = """
    LEFT JOIN creations cr
      ON cr.scope_id = r.scope_id AND cr.llm_id = r.parent_llm_type_id
    LEFT JOIN sessions s
      ON s.scope_id = r.scope_id
    LEFT JOIN nodes n
      ON n.scope_id = r.scope_id AND n.node_id = r.spatial_parent_node_id
"""


def count_llm_trace_rows(
    con: DuckDBPyConnection,
    *,
    session_id: str | None = None,
    node_id: str | None = None,
    flow_names: list[str] | None = None,
    node_names: list[str] | None = None,
    model_names: list[str] | None = None,
    statuses: list[LLMTraceStatus] | None = None,
    since: float | None = None,
    until: float | None = None,
) -> int:
    """Count LLM-call rows matching the filters, ignoring paging.

    Selects no payload columns — the JSON blobs on ``message_input`` / ``output``
    are the expensive part of :func:`list_llm_trace_rows`, and a count needs none
    of them.
    """
    where_clause, params = _llm_trace_filters(
        session_id, node_id, flow_names, node_names, model_names, statuses, since, until
    )
    sql = f"""
    WITH {_llm_calls_cte(with_payload=False)}
    {_LLM_TRACE_JOIN_CTES}
    SELECT COUNT(*) AS total
    FROM llm_calls r
    {_LLM_TRACE_JOINS}
    {where_clause}
    """
    rows = _rows(con, sql, tuple(params), label="count_llm_trace_rows")
    return int(rows[0]["total"]) if rows else 0


def list_llm_trace_rows(
    con: DuckDBPyConnection,
    *,
    limit: int,
    offset: int,
    session_id: str | None = None,
    node_id: str | None = None,
    flow_names: list[str] | None = None,
    node_names: list[str] | None = None,
    model_names: list[str] | None = None,
    statuses: list[LLMTraceStatus] | None = None,
    since: float | None = None,
    until: float | None = None,
    sort_by: LLMTraceSortField = LLMTraceSortField.TIMESTAMP,
    order: SortOrder = SortOrder.DESC,
) -> list[dict[str, Any]]:
    """Return LLM-call rows with server-side filtering, sorting and paging.

    Denormalizes ``flow_name`` / ``flow_id`` from the session and ``node_name``
    from the node onto every row so the client can render, filter, and deep-link
    without a second lookup.

    A failed call takes its model name from the ``llm.creation`` it was made
    through, since it never got far enough to report one back — which is what
    keeps it inside the model filter instead of vanishing from a stream it
    belongs to.

    Sorting is server-side for the same reason the filters are: ordering the
    fifty rows that happened to land on the current page would answer a
    different question than "the most expensive calls in this run".
    """
    where_clause, params = _llm_trace_filters(
        session_id, node_id, flow_names, node_names, model_names, statuses, since, until
    )
    order_clause = _llm_trace_order_clause(sort_by, order)

    sql = f"""
    WITH {_llm_calls_cte(with_payload=True)}
    {_LLM_TRACE_JOIN_CTES}
    SELECT
      r.event_id                                     AS trace_id,
      r.scope_id                                     AS session_id,
      s.flow_id,
      s.flow_name,
      r.spatial_parent_node_id                       AS node_id,
      n.node_name,
      EPOCH(r.timestamp)                             AS timestamp,
      COALESCE(r.reported_model_name, cr.model_name) AS model_name,
      CAST(cr.model_provider AS VARCHAR)             AS model_provider,
      r.status,
      r.exception_name                               AS error_name,
      r.exception_message                            AS error_message,
      COALESCE(r.input_tokens, 0)                    AS input_tokens,
      COALESCE(r.output_tokens, 0)                   AS output_tokens,
      COALESCE(r.total_cost, 0.0)                    AS total_cost,
      r.latency                                      AS latency_seconds,
      CAST(r.message_input AS VARCHAR)               AS message_input_json,
      CAST(r.output AS VARCHAR)                      AS output_json
    FROM llm_calls r
    {_LLM_TRACE_JOINS}
    {where_clause}
    {order_clause}
    LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])
    rows = _rows(
        con,
        sql,
        tuple(params),
        label=f"list_llm_trace_rows(limit={limit}, offset={offset}, sort={sort_by.value}:{order.value})",
    )
    for row in rows:
        row["inputs"] = _parse_json(row.pop("message_input_json"))
        row["output"] = _parse_json(row.pop("output_json"))
    return rows


def get_llm_trace_stats(
    con: DuckDBPyConnection,
    *,
    session_id: str | None = None,
    node_id: str | None = None,
    flow_names: list[str] | None = None,
    node_names: list[str] | None = None,
    model_names: list[str] | None = None,
    statuses: list[LLMTraceStatus] | None = None,
    since: float | None = None,
    until: float | None = None,
) -> dict[str, Any]:
    """Roll-up across every LLM call matching the filters, ignoring paging.

    Shares ``_llm_trace_filters`` and ``_llm_calls_cte`` with the listing and its
    count, so the tiles, the pager total and the rows can never describe three
    different sets — including when the filter is the status itself.

    ``AVG`` skips nulls, so a provider that reports no latency lowers neither the
    average nor the count it is drawn from; the result is null only when nothing
    matching reported a latency at all. A failed call has no latency by the same
    rule, and no tokens or cost to add.
    """
    where_clause, params = _llm_trace_filters(
        session_id, node_id, flow_names, node_names, model_names, statuses, since, until
    )
    sql = f"""
    WITH {_llm_calls_cte(with_payload=False)}
    {_LLM_TRACE_JOIN_CTES}
    SELECT COUNT(*)                                       AS total_calls,
           COUNT(*) FILTER (WHERE r.status = {_STATUS_ERROR_LITERAL})
                                                          AS failed_calls,
           COALESCE(SUM(r.input_tokens), 0)               AS input_tokens,
           COALESCE(SUM(r.output_tokens), 0)              AS output_tokens,
           COALESCE(SUM(r.total_cost), 0.0)               AS total_cost,
           AVG(r.latency)                                 AS avg_latency_seconds,
           MAX(r.latency)                                 AS max_latency_seconds
    FROM llm_calls r
    {_LLM_TRACE_JOINS}
    {where_clause}
    """
    rows = _rows(con, sql, tuple(params), label="get_llm_trace_stats")
    return rows[0] if rows else {}


def list_llm_trace_filter_options(con: DuckDBPyConnection) -> dict[str, list[str]]:
    """Distinct values for the trace filters, computed over the whole stream.

    Three cheap queries rather than one wide one: the lists are unrelated, and
    a single query would either cross-join them or need three passes anyway.

    ``flow_names`` comes from the sessions and so includes flows that made no
    LLM calls at all; ``node_names`` and ``model_names`` come from the calls
    themselves, so they never offer a filter that cannot match — a Tool node has
    no LLM call to list.

    "The calls themselves" means responses *and* failures, matching what the
    listing shows. Drawn from responses alone, an agent whose only call raised
    would be missing from the dropdown while its error sat in the table.
    """
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
        label="trace_filter_options.flow_names",
    )

    node_rows = _rows(
        con,
        """
        WITH resp AS (
          SELECT DISTINCT scope_id, spatial_parent_node_id AS node_id
          FROM llm
          WHERE event_type IN ('llm.response', 'llm.failure')
        ),
        nodes AS (
          SELECT scope_id, node_id, ANY_VALUE(name) AS node_name
          FROM node
          WHERE event_type = 'node.creation'
          GROUP BY scope_id, node_id
        )
        SELECT DISTINCT n.node_name
        FROM resp r
        JOIN nodes n
          ON n.scope_id = r.scope_id AND n.node_id = r.node_id
        WHERE n.node_name IS NOT NULL AND n.node_name <> ''
        ORDER BY n.node_name
        """,
        label="trace_filter_options.node_names",
    )

    model_rows = _rows(
        con,
        f"""
        WITH resp AS (
          SELECT scope_id, parent_llm_type_id, reported_model_name
          FROM llm
          WHERE event_type IN ('llm.response', 'llm.failure')
        ),
        {_LLM_CREATION_JOIN_CTE.lstrip()}
        SELECT DISTINCT COALESCE(r.reported_model_name, cr.model_name) AS model_name
        FROM resp r
        LEFT JOIN creations cr
          ON cr.scope_id = r.scope_id AND cr.llm_id = r.parent_llm_type_id
        WHERE COALESCE(r.reported_model_name, cr.model_name) IS NOT NULL
        ORDER BY model_name
        """,
        label="trace_filter_options.model_names",
    )

    return {
        "flow_names": [r["flow_name"] for r in flow_rows],
        "node_names": [r["node_name"] for r in node_rows],
        "model_names": [r["model_name"] for r in model_rows],
    }
