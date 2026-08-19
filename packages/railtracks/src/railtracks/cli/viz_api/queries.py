"""DuckDB queries backing the visualizer API.

A single :class:`~railtracks.query.EventQuery` is kept alive for the life of the
process. Each request calls :func:`get_query`, which reopens the connection on
first use and after that only re-scans the ``*.jsonl`` files when their newest
mtime has moved. That keeps the per-request cost proportional to the query, not
to the file size — the file scan lands once per write, not once per read.
"""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from railtracks.query import EventQuery, connect

from ..io import print_status, print_warning
from .models import (
    EventSortField,
    LLMTraceSortField,
    LLMTraceStatus,
    MiddlewareKind,
    MiddlewareSortField,
    SortOrder,
)

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection

_NAMESPACES = ["session", "node", "llm", "middleware"]

_query: EventQuery | None = None
_scanned_mtime: float | None = None


def _dir_mtime(events_dir: Path) -> float | None:
    """Newest mtime across ``events_dir/*.jsonl``, or ``None`` when empty."""
    files = list(events_dir.glob("*.jsonl"))
    if not files:
        return None
    return max(f.stat().st_mtime for f in files)


def get_query(events_dir: Path) -> EventQuery:
    """Return a shared :class:`EventQuery`, refreshing when the source files change.

    First call opens the DuckDB connection and registers the four namespace
    views. Subsequent calls compare the newest ``*.jsonl`` mtime against the
    last scan and call ``refresh()`` only when it has moved.
    """
    global _query, _scanned_mtime
    mtime = _dir_mtime(events_dir)
    if _query is None:
        _query = connect(events_dir, _NAMESPACES)
        _scanned_mtime = mtime
        return _query
    if mtime != _scanned_mtime:
        _query.refresh()
        _scanned_mtime = mtime
    return _query


def close_query() -> None:
    """Close the shared connection. Called from shutdown handlers and tests."""
    global _query, _scanned_mtime
    if _query is not None:
        _query.close()
        _query = None
    _scanned_mtime = None


def _rows(
    con: DuckDBPyConnection,
    sql: str,
    params: tuple[Any, ...] = (),
    label: str | None = None,
) -> list[dict[str, Any]]:
    """Execute ``sql`` and return the rows as dicts.

    When ``label`` is set, the call is timed and logged to the server console —
    handy while demoing what fires per request. Internal helpers that don't
    hit the event data (e.g. constant SELECTs used as fallbacks) leave ``label``
    unset so they don't add noise.
    """
    t0 = time.perf_counter()
    cur = con.execute(sql, params)
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    if label:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        print_status(f"  ↳ {label}: {len(rows)} row(s) in {elapsed_ms:.1f}ms")
    return rows


# ---------------------------------------------------------------------------
# Shared filter / ordering plumbing
#
# The listing endpoints (sessions, LLM traces, events) are different queries
# over different grains, but they narrow and order by the same rules. These
# helpers exist so each rule has one implementation: an `IN` list built with the
# right number of placeholders, a half-open time window, and an ordering that
# pages deterministically. A second copy of any of them would eventually
# disagree with the first, which is the failure the shared `WHERE` clause
# discipline elsewhere in this module exists to prevent.
# ---------------------------------------------------------------------------


def _in_clause(column: str, values: Sequence[Any]) -> str:
    """``column IN (?, ?, …)`` with one placeholder per value.

    Callers ``params.extend(values)`` alongside. Nothing user-supplied is ever
    interpolated — the values travel as bound parameters, only the placeholder
    count is computed.
    """
    return f"{column} IN ({', '.join('?' for _ in values)})"


def _window_predicates(
    column: str,
    since: float | None,
    until: float | None,
) -> tuple[list[str], list[Any]]:
    """The ``since <= column < until`` window every list endpoint shares.

    Half-open deliberately: ``since`` inclusive and ``until`` exclusive, so
    adjacent windows tile the timeline without a row falling in both. Each
    caller passes the expression its own grain is bounded on — sessions bind
    ``start_time`` (a session is in the window if it *started* there), LLM
    traces and events bind the call's or the event's own stamp.
    """
    predicates: list[str] = []
    params: list[Any] = []
    if since is not None:
        predicates.append(f"{column} >= ?")
        params.append(since)
    if until is not None:
        predicates.append(f"{column} < ?")
        params.append(until)
    return predicates, params


def _order_clause(column: str, order: SortOrder, tiebreakers: Sequence[str]) -> str:
    """``ORDER BY`` for a paged listing, with deterministic tie-breaking.

    Two details that matter, and both are why this is shared rather than
    written per endpoint:

    * **NULLS LAST in both directions.** A null is "not reported", not a low
      value — sorting a null latency to the top of an ascending list would read
      as "fastest".
    * **A unique final tiebreaker.** Without one, two rows with equal sort keys
      can swap places between two queries, and a paged client then sees one row
      twice and another not at all. Callers end ``tiebreakers`` with a column
      that is unique per row.
    """
    direction = "ASC" if order is SortOrder.ASC else "DESC"
    return "ORDER BY " + ", ".join([f"{column} {direction} NULLS LAST", *tiebreakers])


#: Flow name/id per session, for denormalizing onto a row that carries only a
#: ``scope_id``. Grouped by the join key — see :data:`_LLM_TRACE_JOIN_CTES`.
_SESSION_JOIN_CTE = """
    sessions AS (
      SELECT scope_id,
             ANY_VALUE(flow_name) AS flow_name,
             ANY_VALUE(flow_id)   AS flow_id
      FROM session
      WHERE event_type = 'session.started'
      GROUP BY scope_id
    )"""

#: Node display name per (session, node). Grouped by the join key.
_NODE_JOIN_CTE = """
    nodes AS (
      SELECT scope_id,
             node_id,
             ANY_VALUE(name) AS node_name
      FROM node
      WHERE event_type = 'node.creation'
      GROUP BY scope_id, node_id
    )"""

#: Each node invocation as a half-open interval, so an event with no node key of
#: its own can be attributed to the node that was running when it fired.
#:
#: **Why this exists.** A middleware in the LLM band carries only
#: ``spatial_parent_llm_invoke_id``, and the node is recovered by hopping through
#: that invocation's ``llm.*`` events. When a guard *blocks*, there are no such
#: events — the guard runs before ``llm.invocation`` fires, so the hop finds
#: nothing and the decision is dropped. That is not a rounding error in the data:
#: measured over 104 guard decisions, the hop resolved 91 and dropped 13, and
#: **all 13 were blocks**. The node-level guardrail marker could therefore never
#: show a block, which is what had a session tree reporting "all allowed" beside a
#: Middleware column that correctly said one call was stopped.
#:
#: **Why containment and not "the most recent invocation".** Node invocations
#: overlap — 122 overlapping pairs across 47 of 109 sessions on the measured store
#: — so the latest preceding ``node.invocation`` is often a node that had already
#: returned. Taking the innermost interval that *contains* the timestamp instead
#: reproduces what a call stack would say. Both were checked against the LLM hop
#: wherever both resolve: containment agreed 89 of 89, the latest-preceding rule
#: 81 of 91.
#:
#: ``node.destruction`` closes the interval alongside response/failure because a
#: node that raised may emit only the former.
#: This constant carries no trailing comma. Composers insert commas between
#: CTE fragments explicitly (via ``",".join`` or ``+ ","``), so a fragment
#: chained differently — as the last CTE, or the first — needs no per-caller
#: fix-up. The old convention embedded a trailing comma here and forced two
#: callers to strip it back off with ``.rstrip(",")``, which broke silently
#: the moment the constant's punctuation changed.
_NODE_SPAN_CTE = """
    node_spans AS (
      SELECT scope_id,
             CAST(parent_node_id AS VARCHAR) AS node_id,
             MIN(timestamp) FILTER (WHERE event_type = 'node.invocation')  AS opened_at,
             MAX(timestamp) FILTER (WHERE event_type IN ('node.response',
                                                        'node.failure',
                                                        'node.destruction')) AS closed_at
      FROM node
      WHERE parent_node_id IS NOT NULL
      GROUP BY scope_id, parent_node_id
      HAVING MIN(timestamp) FILTER (WHERE event_type = 'node.invocation') IS NOT NULL
    )"""

#: Middleware name per ``middleware_type_id``, the only place a name is recorded.
#:
#: ``middleware.creation`` is the *sole* event carrying ``middleware_name``:
#: every other middleware event — invocation, response, failure, guard decision —
#: identifies its middleware by ``parent_middleware_type_id`` alone. So filtering
#: or searching events by a name is impossible without this join, and a text
#: search for one matches only its creations: 81 rows on a stream where that
#: middleware ran 79 times.
#:
#: Grouped by the join key, and **globally rather than per session**, for the two
#: reasons :func:`_middleware_rows_cte` documents: a type_id gets a creation
#: event per process, and a module-level middleware registers once per process so
#: later sessions carry invocations whose creation lives in another session's
#: file. Shared by the middleware endpoints and the event log so the two cannot
#: disagree about which events belong to a name.
_MIDDLEWARE_NAME_CTE = """
    mw_names AS (
      SELECT middleware_type_id         AS type_id,
             ANY_VALUE(middleware_name) AS middleware_name
      FROM middleware
      WHERE event_type = 'middleware.creation'
        AND middleware_type_id IS NOT NULL
      GROUP BY middleware_type_id
    )"""


# ---------------------------------------------------------------------------
# Session summary rows
# ---------------------------------------------------------------------------

_SESSION_SUMMARY_CTE = """
WITH started AS (
  SELECT scope_id,
         timestamp AS started_at,
         flow_name,
         flow_id,
         session_name,
         entry_point_name
  FROM session
  WHERE event_type = 'session.started'
),
completed AS (
  SELECT scope_id,
         timestamp AS ended_at,
         status,
         duration_seconds
  FROM session
  WHERE event_type = 'session.completed'
),
llm_agg AS (
  SELECT scope_id,
         SUM(COALESCE(input_tokens, 0)) AS input_tokens,
         SUM(COALESCE(output_tokens, 0)) AS output_tokens,
         SUM(COALESCE(total_cost, 0.0)) AS total_cost
  FROM llm
  WHERE event_type = 'llm.response'
  GROUP BY scope_id
),
node_agg AS (
  SELECT scope_id,
         COUNT(*) AS node_count
  FROM node
  WHERE event_type = 'node.creation'
  GROUP BY scope_id
)
SELECT s.scope_id                                    AS session_id,
       s.flow_name,
       s.flow_id,
       s.session_name,
       s.entry_point_name,
       EPOCH(s.started_at)                           AS start_time,
       EPOCH(c.ended_at)                             AS end_time,
       CAST(c.status AS VARCHAR)                     AS raw_status,
       c.duration_seconds                            AS duration,
       COALESCE(l.input_tokens, 0)                   AS input_tokens,
       COALESCE(l.output_tokens, 0)                  AS output_tokens,
       COALESCE(l.total_cost, 0.0)                   AS total_cost,
       COALESCE(n.node_count, 0)                     AS node_count,
       -- The rolled-up status, in SQL rather than Python, so the same
       -- definition serves the row, the status filter and the stat tiles. Two
       -- copies of this CASE would eventually disagree about what "Failed"
       -- counts, and the tiles would contradict the table they sit above.
       CASE
         WHEN c.status IS NULL AND c.ended_at IS NULL   THEN 'Running'
         WHEN c.status IS NULL                          THEN 'Completed'
         WHEN LOWER(CAST(c.status AS VARCHAR)) = 'success' THEN 'Completed'
         WHEN LOWER(CAST(c.status AS VARCHAR)) = 'failure' THEN 'Failed'
         ELSE 'Running'
       END                                           AS status
FROM started s
LEFT JOIN completed c USING (scope_id)
LEFT JOIN llm_agg   l USING (scope_id)
LEFT JOIN node_agg  n USING (scope_id)
"""


def _session_filters(
    flow_names: list[str] | None,
    entry_point_names: list[str] | None,
    statuses: list[str] | None,
    since: float | None = None,
    until: float | None = None,
) -> tuple[str, list[Any]]:
    """Build the ``WHERE`` clause shared by the session list and its stats.

    Both go through here so a stat tile can never describe a different set of
    sessions than the table underneath it. Predicates are written against the
    outer query's columns, so callers must wrap ``_SESSION_SUMMARY_CTE`` in a
    subquery aliased ``s`` — see :func:`_filtered_sessions_sql`.

    ``since`` / ``until`` are unix seconds and bound ``start_time``: a session
    is in the window if it *started* in it. A run still going after eight days
    therefore drops out of "last 7 days", which is what that phrase means — the
    alternative, matching on overlap, would keep one long-running session in
    every window it touched and make the counts above the table unexplainable.
    ``since`` is inclusive and ``until`` exclusive, so adjacent windows tile the
    timeline without double-counting a row on the boundary.
    """
    predicates: list[str] = []
    params: list[Any] = []
    if flow_names:
        predicates.append(_in_clause("s.flow_name", flow_names))
        params.extend(flow_names)
    if entry_point_names:
        predicates.append(_in_clause("s.entry_point_name", entry_point_names))
        params.extend(entry_point_names)
    if statuses:
        predicates.append(_in_clause("s.status", statuses))
        params.extend(statuses)
    window, window_params = _window_predicates("s.start_time", since, until)
    predicates.extend(window)
    params.extend(window_params)
    return ("WHERE " + " AND ".join(predicates) if predicates else "", params)


def _filtered_sessions_sql(where_clause: str) -> str:
    """``_SESSION_SUMMARY_CTE`` wrapped so the filters can see its derived
    columns — ``status`` is a CASE expression and cannot be filtered inside the
    query that computes it."""
    return f"SELECT * FROM ({_SESSION_SUMMARY_CTE}) s {where_clause}"


def list_session_rows(
    con: DuckDBPyConnection,
    *,
    flow_names: list[str] | None = None,
    entry_point_names: list[str] | None = None,
    statuses: list[str] | None = None,
    since: float | None = None,
    until: float | None = None,
) -> list[dict[str, Any]]:
    """Session rows, newest first, narrowed server-side.

    The filters used to run in the browser over the full list. That was
    survivable while the endpoint returned every session, but it cannot produce
    honest stat tiles — those have to be computed over the same predicate, not
    over whatever the client happened to hold.
    """
    where_clause, params = _session_filters(
        flow_names, entry_point_names, statuses, since, until
    )
    return _rows(
        con,
        _filtered_sessions_sql(where_clause) + " ORDER BY start_time DESC",
        tuple(params),
        label="list_session_rows",
    )


def get_session_stats(
    con: DuckDBPyConnection,
    *,
    flow_names: list[str] | None = None,
    entry_point_names: list[str] | None = None,
    statuses: list[str] | None = None,
    since: float | None = None,
    until: float | None = None,
) -> dict[str, Any]:
    """Roll-up across every session matching the filters, ignoring paging.

    Computed here rather than by summing the rows in the browser: the client
    would be re-deriving what the server already knows, and it would silently
    start lying the day this list is paginated.
    """
    where_clause, params = _session_filters(
        flow_names, entry_point_names, statuses, since, until
    )
    sql = f"""
    SELECT COUNT(*)                                           AS total_runs,
           COUNT(*) FILTER (WHERE s.status = 'Completed')      AS successes,
           COUNT(*) FILTER (WHERE s.status = 'Failed')         AS failures,
           COUNT(*) FILTER (WHERE s.status = 'Running')        AS running,
           COALESCE(SUM(s.input_tokens), 0)                    AS input_tokens,
           COALESCE(SUM(s.output_tokens), 0)                   AS output_tokens,
           COALESCE(SUM(s.total_cost), 0.0)                    AS total_cost
    FROM ({_filtered_sessions_sql(where_clause)}) s
    """
    rows = _rows(con, sql, tuple(params), label="get_session_stats")
    return rows[0] if rows else {}


def list_session_filter_options(con: DuckDBPyConnection) -> dict[str, list[str]]:
    """Distinct flow names, entry points and statuses across every session.

    Like the trace filters, these come from the whole stream rather than the
    rows in hand, so a selection can always be widened again.
    """
    rows = _rows(
        con,
        f"""
        SELECT DISTINCT flow_name, entry_point_name, status
        FROM ({_SESSION_SUMMARY_CTE}) s
        """,
        label="list_session_filter_options",
    )
    flow_names = sorted({r["flow_name"] for r in rows if r["flow_name"]})
    entry_points = sorted(
        {r["entry_point_name"] for r in rows if r["entry_point_name"]}
    )
    statuses = sorted({r["status"] for r in rows if r["status"]})
    return {
        "flow_names": flow_names,
        "entry_point_names": entry_points,
        "statuses": statuses,
    }


def get_session_row(con: DuckDBPyConnection, session_id: str) -> dict[str, Any] | None:
    rows = _rows(
        con,
        _SESSION_SUMMARY_CTE + "WHERE s.scope_id = ?",
        (session_id,),
        label=f"get_session_row({session_id[:8]})",
    )
    return rows[0] if rows else None


# ---------------------------------------------------------------------------
# Nodes for a session
# ---------------------------------------------------------------------------


def list_session_node_rows(
    con: DuckDBPyConnection, session_id: str
) -> list[dict[str, Any]]:
    """One row per node in a session: identity, parent, timing, and status.

    NB: on the ``node.invocation`` / ``.response`` / ``.destruction`` / ``.failure``
    events, ``node_id`` is null. Those events resolve their ``parent`` via
    ``node_parent(scope)``, which returns the *current* node's id — so the
    node's own id sits under ``parent_node_id``, not ``node_id``.

    Tree parent is ``node.invocation.spatial_parent_node_id`` — a null value
    marks a root. ``failed`` is true when any ``node.failure`` event was seen.
    """
    sql = """
    WITH creation AS (
      SELECT node_id, name, node_type, timestamp AS created_at
      FROM node
      WHERE event_type = 'node.creation' AND scope_id = ?
    ),
    invocation AS (
      SELECT parent_node_id                     AS node_id,
             MAX(spatial_parent_node_id)        AS parent_node_id,
             MIN(timestamp)                     AS started_at
      FROM node
      WHERE event_type = 'node.invocation' AND scope_id = ?
      GROUP BY parent_node_id
    ),
    destruction AS (
      SELECT parent_node_id                     AS node_id,
             MAX(duration_seconds)              AS duration_seconds,
             MAX(timestamp)                     AS ended_at
      FROM node
      WHERE event_type = 'node.destruction' AND scope_id = ?
      GROUP BY parent_node_id
    ),
    failure AS (
      SELECT DISTINCT parent_node_id AS node_id
      FROM node
      WHERE event_type = 'node.failure' AND scope_id = ?
    )
    SELECT c.node_id,
           c.name,
           c.node_type,
           i.parent_node_id,
           d.duration_seconds,
           EPOCH(c.created_at)              AS created_at,
           EPOCH(i.started_at)              AS started_at,
           EPOCH(d.ended_at)                AS ended_at,
           (f.node_id IS NOT NULL)          AS failed
    FROM creation c
    LEFT JOIN invocation  i USING (node_id)
    LEFT JOIN destruction d USING (node_id)
    LEFT JOIN failure     f USING (node_id)
    ORDER BY created_at ASC
    """
    return _rows(
        con,
        sql,
        (session_id, session_id, session_id, session_id),
        label=f"list_session_node_rows({session_id[:8]})",
    )


# ---------------------------------------------------------------------------
# LLM aggregates per node in a session
# ---------------------------------------------------------------------------


def list_llm_totals_by_node(
    con: DuckDBPyConnection, session_id: str
) -> list[dict[str, Any]]:
    """LLM cost/token roll-up per node, plus the model info of the final
    response for that node."""
    sql = f"""
    WITH resp AS (
      SELECT scope_id,
             spatial_parent_node_id AS node_id,
             timestamp,
             parent_llm_type_id,
             input_tokens,
             output_tokens,
             total_cost,
             reported_model_name
      FROM llm
      WHERE event_type = 'llm.response' AND scope_id = ?
    ),
    agg AS (
      SELECT node_id,
             SUM(COALESCE(input_tokens, 0))   AS input_tokens,
             SUM(COALESCE(output_tokens, 0))  AS output_tokens,
             SUM(COALESCE(total_cost, 0.0))   AS total_cost,
             MAX(timestamp)                   AS last_at
      FROM resp
      GROUP BY node_id
    ),
    {_LLM_CREATION_JOIN_CTE.lstrip()},
    last_resp AS (
      SELECT r.scope_id,
             r.node_id,
             r.parent_llm_type_id,
             r.reported_model_name
      FROM resp r
      JOIN agg USING (node_id)
      WHERE r.timestamp = agg.last_at
    )
    SELECT a.node_id,
           a.input_tokens,
           a.output_tokens,
           a.total_cost,
           COALESCE(lr.reported_model_name, cr.model_name) AS model_name,
           CAST(cr.model_provider AS VARCHAR)              AS model_provider
    FROM agg a
    LEFT JOIN last_resp lr USING (node_id)
    LEFT JOIN creations cr
      ON cr.scope_id = lr.scope_id AND cr.llm_id = lr.parent_llm_type_id
    """
    return _rows(
        con,
        sql,
        (session_id,),
        label=f"list_llm_totals_by_node({session_id[:8]})",
    )


# ---------------------------------------------------------------------------
# Node details — inputs / outputs
# ---------------------------------------------------------------------------


def get_node_row(
    con: DuckDBPyConnection, session_id: str, node_id: str
) -> dict[str, Any] | None:
    sql = """
    SELECT node_id, name, node_type
    FROM node
    WHERE event_type = 'node.creation' AND scope_id = ? AND node_id = ?
    """
    rows = _rows(
        con,
        sql,
        (session_id, node_id),
        label=f"get_node_row({node_id[:8]})",
    )
    return rows[0] if rows else None


def get_agent_llm_details(
    con: DuckDBPyConnection, session_id: str, node_id: str
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """For an Agent node, return (final_response_row_or_none, totals_dict).

    The final row carries ``message_input`` and ``output`` for the details
    panel. Totals sum tokens/cost across every LLM response emitted from the
    node's scope.
    """
    sql = f"""
    WITH resp AS (
      SELECT scope_id,
             timestamp,
             parent_llm_type_id,
             message_input,
             output,
             input_tokens,
             output_tokens,
             total_cost,
             reported_model_name
      FROM llm
      WHERE event_type = 'llm.response'
        AND scope_id = ?
        AND spatial_parent_node_id = ?
    ),
    totals AS (
      SELECT SUM(COALESCE(input_tokens, 0))   AS input_tokens,
             SUM(COALESCE(output_tokens, 0))  AS output_tokens,
             SUM(COALESCE(total_cost, 0.0))   AS total_cost
      FROM resp
    ),
    {_LLM_CREATION_JOIN_CTE.lstrip()}
    SELECT r.timestamp,
           CAST(r.message_input AS VARCHAR)    AS message_input_json,
           CAST(r.output AS VARCHAR)           AS output_json,
           COALESCE(r.reported_model_name, cr.model_name) AS model_name,
           CAST(cr.model_provider AS VARCHAR)  AS model_provider,
           t.input_tokens,
           t.output_tokens,
           t.total_cost
    FROM resp r
    CROSS JOIN totals t
    LEFT JOIN creations cr
      ON cr.scope_id = r.scope_id AND cr.llm_id = r.parent_llm_type_id
    ORDER BY r.timestamp DESC
    LIMIT 1
    """
    rows = _rows(
        con,
        sql,
        (session_id, node_id),
        label=f"get_agent_llm_details({node_id[:8]})",
    )
    if not rows:
        totals = _rows(
            con,
            """
            SELECT 0 AS input_tokens, 0 AS output_tokens, 0.0 AS total_cost
            """,
        )[0]
        return None, totals
    row = rows[0]
    totals = {
        "input_tokens": row["input_tokens"],
        "output_tokens": row["output_tokens"],
        "total_cost": row["total_cost"],
    }
    final = {
        "message_input": _parse_json(row["message_input_json"]),
        "output": _parse_json(row["output_json"]),
        "model_name": row["model_name"],
        "model_provider": row["model_provider"],
    }
    return final, totals


def get_tool_io(
    con: DuckDBPyConnection, session_id: str, node_id: str
) -> dict[str, Any] | None:
    """For a Tool node, return the args/kwargs it was called with and its
    ``response`` from the destruction event."""
    # ``node.invocation`` / ``.response`` / ``.destruction`` carry their owning
    # node id under ``parent_node_id`` (see ``list_session_node_rows``).
    sql = """
    WITH invocation AS (
      SELECT CAST(args AS VARCHAR)   AS args_json,
             CAST(kwargs AS VARCHAR) AS kwargs_json,
             timestamp
      FROM node
      WHERE event_type = 'node.invocation'
        AND scope_id = ?
        AND parent_node_id = ?
      ORDER BY timestamp ASC
      LIMIT 1
    ),
    result AS (
      SELECT CAST(response AS VARCHAR) AS response_json
      FROM node
      WHERE event_type IN ('node.destruction', 'node.response')
        AND scope_id = ?
        AND parent_node_id = ?
      ORDER BY timestamp DESC
      LIMIT 1
    )
    SELECT i.args_json,
           i.kwargs_json,
           r.response_json
    FROM invocation i
    LEFT JOIN result r ON TRUE
    """
    rows = _rows(
        con,
        sql,
        (session_id, node_id, session_id, node_id),
        label=f"get_tool_io({node_id[:8]})",
    )
    if not rows:
        return None
    row = rows[0]
    return {
        "args": _parse_json(row["args_json"]) or [],
        "kwargs": _parse_json(row["kwargs_json"]) or {},
        "response": _parse_json(row["response_json"]),
    }


# ---------------------------------------------------------------------------
# LLM traces — one row per round trip, denormalized with session & node
# ---------------------------------------------------------------------------


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
                  THEN '{LLMTraceStatus.ERROR.value}'
                  ELSE '{LLMTraceStatus.SUCCESS.value}'
             END AS status{payload}
      FROM llm
      WHERE event_type IN ('llm.response', 'llm.failure')
    ),"""


#: Model name/provider per (session, LLM), grouped by the join key.
#:
#: Every ``llm.creation`` reader shares this one CTE — the trace listing, the
#: per-node totals, the details panel, and the model-name filter option. It
#: used to be inlined four different ways, three of them session-scoped by a
#: ``WHERE scope_id = ?`` inside the CTE and one global. The join key now
#: always carries ``scope_id``, so a caller filters by joining rather than by
#: re-parameterising the CTE, and a repeated ``llm.creation`` cannot duplicate
#: a decorated row from either direction.
_LLM_CREATION_JOIN_CTE = """
    creations AS (
      SELECT scope_id,
             llm_id,
             ANY_VALUE(model_provider) AS model_provider,
             ANY_VALUE(model_name)     AS model_name
      FROM llm
      WHERE event_type = 'llm.creation'
      GROUP BY scope_id, llm_id
    )"""

#: The denormalizing CTEs shared by the LLM trace listing and its count.
#:
#: Every one of them is grouped by its join key. The stream can carry a repeated
#: ``llm.creation``, ``session.started`` or ``node.creation`` for the same
#: entity, and an ungrouped join then fans a single LLM response out into as
#: many rows as it matched — the bug that once had ``/api/llm-traces`` reporting
#: 44 rows for a 30-call stream. Add a join here and group it the same way.
#:
#: The session and node blocks are shared with the events listing, which
#: denormalizes flow and node onto its rows by the same keys — see
#: :data:`_EVENT_JOIN_CTES`.
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
           COUNT(*) FILTER (WHERE r.status = '{LLMTraceStatus.ERROR.value}')
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


# ---------------------------------------------------------------------------
# Events — the raw stream, one row per event
# ---------------------------------------------------------------------------
#
# This is the one endpoint that reads the ``events`` view rather than a
# namespace view, and that is the point of it: ``events`` is the raw envelope
# plus the untyped ``payload``, so it carries *every* event in the stream —
# including one whose namespace the registry does not declare yet. A log built
# on the namespace views could only ever show the four namespaces
# ``_NAMESPACES`` lists, which makes it useless for the job a log exists to do:
# seeing the event you just added and have not registered.
#
# It also means the time column is the envelope's ``stamp`` rather than the
# payload's ``timestamp``. ``stamp`` is on every event unconditionally, where
# ``timestamp`` is a registry-declared payload key and would be null for an
# unregistered namespace.


#: SQL for each sortable measure, in terms of the ``ev`` alias ``e``. Keyed by
#: the enum, so nothing user-supplied reaches the ``ORDER BY``.
_EVENT_SORT_COLUMNS = {
    EventSortField.TIMESTAMP: "e.stamp",
    EventSortField.EVENT_TYPE: "e.event_type",
    EventSortField.PAYLOAD_BYTES: "e.payload_bytes",
}

#: The denormalizing CTEs for the events listing — shared with the LLM traces
#: listing, and grouped by their join key for the same reason. See
#: :data:`_LLM_TRACE_JOIN_CTES`.
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
    without a second lookup. Both joins are grouped by their join key — see
    :data:`_LLM_TRACE_JOIN_CTES` for the fan-out this avoids.

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


# ---------------------------------------------------------------------------
# Middleware — one row per middleware, rolled up
# ---------------------------------------------------------------------------
#
# The grain here is a *middleware*, not one of its invocations: the question the
# page answers ("which middleware ran, how often, and what did they block") is
# about a set of invocations, so the set is the row. The per-invocation stream is
# already served, at event grain, by `/api/events?namespace=middleware`.
#
# Three derivations happen here that the framework does not serve, and all three
# are computed over the *whole* store rather than the filtered window, because
# they are properties of the middleware rather than of the window. A window that
# happened to exclude a guard's decision events would otherwise reclassify the
# guard as a plain wrapper.

#: Middleware the framework injects itself, on every node and every model chain
#: respectively. They exist to emit the very events being read here, so they
#: appear in every session and carry no information about the code under
#: observation — a column that says the same thing on every row.
#:
#: An explicit list rather than an underscore-prefix rule, deliberately: guards
#: captured before the naming fix that landed on main report as
#: ``_middleware_fn``, so a prefix rule would silently swallow real user
#: guardrails along with these two.
_INTERNAL_MIDDLEWARE_NAMES = ("_observe_middleware", "_llm_observe")

#: Kind per ``middleware_type_id``, as a precedence ladder over the *specialised*
#: event types a middleware emits.
#:
#: Most-specific-wins is load-bearing, not defensive. ``@before_llm`` and
#: ``@after_llm`` are both built on ``@wrap_llm``, so each emits its own
#: specialised pair *and* the generic ``middleware.model.invocation`` /
#: ``.response``. Measured on one agent run with every decorator stacked,
#: ``middleware.model.invocation`` fires four times — once each for the
#: ``@before_llm``, the ``@after_llm``, the ``@wrap_llm`` and ``_llm_observe``.
#: Rewriting these ``LIKE``s as equality tests would label a ``@before_llm`` a
#: plain model wrapper.
#:
#: The final band fallback catches an LLM-band middleware that emits no
#: specialised event at all, and on the current store that is the *common* case
#: rather than the edge. Counted over 109 sessions: nothing emits
#: ``middleware.model.input.*`` or ``middleware.model.output.*``, and the only
#: emitter of the generic ``middleware.model.*`` is the framework's own
#: ``_llm_observe``. Every user LLM middleware there — ``force_uppercase``,
#: ``counter``, ``print_message``, ``record_response`` — emits nothing but
#: ``middleware.invocation`` / ``.response`` under
#: ``spatial_parent_type = 'llm_and_middleware'``, so it lands on this rung
#: as ``llm_wrapper``.
#:
#: The consequence is worth stating plainly rather than discovering: a
#: ``@before_llm`` is reported as a request transform **only when the framework
#: emits the specialised pair for it**, and where it does not, the honest answer
#: from the stream is "something wrapped the LLM call". The ladder is not guessing
#: past what was recorded, and the ``.input.%`` / ``.output.%`` rungs are kept
#: because they are right the moment those events appear — they carry
#: ``.invocation``, ``.response`` *and* ``.failure``, all matched by the wildcard.
_MIDDLEWARE_KIND_CASE = """
      CASE
        WHEN BOOL_OR(event_type LIKE 'middleware.guard.input.%')    THEN 'input_guard'
        WHEN BOOL_OR(event_type LIKE 'middleware.guard.output.%')   THEN 'output_guard'
        WHEN BOOL_OR(event_type LIKE 'middleware.model.input.%')    THEN 'request_transform'
        WHEN BOOL_OR(event_type LIKE 'middleware.model.output.%')   THEN 'response_transform'
        WHEN BOOL_OR(event_type LIKE 'middleware.regular.output.%') THEN 'result_hook'
        WHEN BOOL_OR(event_type LIKE 'middleware.model.%')          THEN 'llm_wrapper'
        WHEN BOOL_OR(spatial_parent_type = 'llm_and_middleware')    THEN 'llm_wrapper'
        ELSE 'node_wrapper'
      END"""

#: SQL for each sortable measure, in terms of the grouped subquery's own columns.
#: Keyed by the enum, so nothing user-supplied reaches the ``ORDER BY``.
_MIDDLEWARE_SORT_COLUMNS = {
    MiddlewareSortField.INVOCATIONS: "g.invocations",
    MiddlewareSortField.BLOCKS: "g.blocks",
    MiddlewareSortField.NAME: "g.middleware_name",
    MiddlewareSortField.LAST_SEEN: "g.last_seen",
}


def _middleware_rows_cte() -> str:
    """The middleware events every middleware endpoint is built from.

    Four things are resolved here so the listing, its count and its stats read
    one definition:

    * **Name**, from ``middleware.creation`` joined on ``middleware_type_id`` and
      **grouped by it**. The grouping is required, not tidiness: a type_id gets a
      creation event per process, so ``_observe_middleware`` alone has 225
      creations across 33 type_ids on a 3,887-event store, and an ungrouped join
      would fan each of its events out 7-fold. The join is global rather than
      session-scoped for the same reason it resolves at all —
      ``_llm_observe`` is a module-level singleton whose registration fires once
      per *process*, so sessions after the first carry invocations whose creation
      lives in another session's file. Measured: 0 of 1,545 events with a parent
      type_id fail to resolve globally.

      It stays a ``LEFT`` join with a fallback label anyway. An unresolvable
      middleware should appear as an unnamed row rather than vanish — a stream
      truncated mid-session is the case, and silently dropping its events would
      under-report every count on the page.

    * **Kind and band**, per :data:`_MIDDLEWARE_KIND_CASE`, over every event for
      the type_id regardless of the request's filters.

    * **The node**, which middleware events do not carry directly. Node-band
      events name it under ``spatial_parent_node_id``; LLM-band events name only
      the LLM invocation they wrapped, under ``spatial_parent_llm_invoke_id``, and
      the ``llm.*`` events for that invocation name the node — the same hop the
      event log makes. Grouped by the join key, like every join here. When the hop
      finds nothing, :data:`_NODE_SPAN_CTE` supplies the node that was running;
      see there for why that is a containment test and not a nearest-preceding one.

    * **The decision**, flattened out of the ``decision`` payload into ``action``
      and ``reason``. Only ``middleware.guard.*.response`` carries one; every
      other event contributes null, which is what keeps ``allows`` /
      ``transforms`` / ``blocks`` at zero for a non-guard rather than absent.

    * **Whether the middleware itself raised**, which is the part that took a
      correction. Every invocation ends in exactly one of ``middleware.response``
      or ``middleware.failure`` — that pair is the pass/stop signal, and reading
      only guard decisions meant a middleware that stopped a run by raising
      reported "passed". A `@wrap_node` that raises ``Exception("Negative numbers
      are not allowed.")`` is on this store, and it read as having passed the call
      it had just killed.

      A failure alone is not enough to blame it, though. An exception unwinds
      through *every* enclosing middleware, so one guard block emits a failure for
      the guard and one for each layer outside it — 5 deep on this store, and 34
      of 71 failures are that collateral. And a middleware wrapping a node that
      raised on its own reports a failure without having done anything: 45 of
      ``_observe_middleware``'s failures are the wrapped node's ``ValueError``
      passing through.

      ``raised_here`` separates them by asking whether what it wrapped failed
      first: if a ``node.failure`` or ``llm.failure`` in the same session carries
      the same exception message at or before this event, the exception came from
      inside and the middleware only sat in its path. Checked against the guard
      decisions, which are authoritative: all 14 blocks on the store are also
      ``raised_here`` or carry ``action = 'block'``, and no wrapper is.
    """
    return (
        _MIDDLEWARE_NAME_CTE
        + ","
        + _NODE_SPAN_CTE
        + ","
        + """
    mw_kinds AS (
      SELECT parent_middleware_type_id           AS type_id,
             """
        + _MIDDLEWARE_KIND_CASE
        + """   AS kind,
             CASE WHEN BOOL_OR(spatial_parent_type = 'llm_and_middleware')
                  THEN 'llm' ELSE 'node' END   AS band
      FROM middleware
      WHERE parent_middleware_type_id IS NOT NULL
      GROUP BY parent_middleware_type_id
    ),
    mw_llm_nodes AS (
      SELECT scope_id,
             parent_llm_invoke_id                AS llm_invoke_id,
             ANY_VALUE(spatial_parent_node_id)   AS node_id
      FROM llm
      WHERE event_type IN ('llm.invocation', 'llm.response', 'llm.failure')
        AND parent_llm_invoke_id IS NOT NULL
        AND spatial_parent_node_id IS NOT NULL
      GROUP BY scope_id, parent_llm_invoke_id
    ),
    -- What the middleware wrapped, when that failed, and with which exception.
    -- Only the message is compared: the same exception object is re-reported at
    -- each layer, so identity is the message plus the session plus the ordering.
    callee_failures AS (
      SELECT scope_id, timestamp, exception_message
      FROM node
      WHERE event_type = 'node.failure' AND exception_message IS NOT NULL
      UNION ALL
      SELECT scope_id, timestamp, exception_message
      FROM llm
      WHERE event_type = 'llm.failure' AND exception_message IS NOT NULL
    ),
    mw_events AS (
      SELECT ev.event_id,
             ev.event_type,
             ev.scope_id,
             ev.timestamp,
             ev.parent_middleware_type_id,
             ev.parent_middleware_invoke_id,
             ev.spatial_parent_node_id,
             ev.spatial_parent_llm_invoke_id,
             ev.decision->>'action'         AS action,
             ev.decision->>'reason'         AS reason,
             ev.event_type LIKE '%.failure' AS is_failure,
             ev.exception_message,
             ev.exception_name
      FROM middleware ev
      WHERE ev.parent_middleware_type_id IS NOT NULL
    ),
    -- The innermost node invocation open when the event fired, for the events that
    -- name no node and whose LLM invocation produced no `llm.*` to hop through.
    mw_enclosing AS (
      SELECT e.event_id,
             s.node_id,
             ROW_NUMBER() OVER (PARTITION BY e.event_id ORDER BY s.opened_at DESC) AS depth
      FROM mw_events e
      JOIN node_spans s
        ON s.scope_id = e.scope_id
       AND e.timestamp >= s.opened_at
       AND (s.closed_at IS NULL OR e.timestamp <= s.closed_at)
      WHERE e.spatial_parent_node_id IS NULL
    ),
    m AS (
      SELECT ev.event_id,
             ev.event_type,
             ev.scope_id                                       AS session_id,
             ev.timestamp,
             ev.parent_middleware_type_id                      AS type_id,
             ev.parent_middleware_invoke_id                     AS invoke_id,
             -- One invocation, named by the pair rather than the id alone: the id
             -- is a per-process UUID, so the session is what makes it unique.
             ev.scope_id || '|' ||
               CAST(ev.parent_middleware_invoke_id AS VARCHAR)   AS invocation_key,
             COALESCE(nm.middleware_name,
                      'middleware ' || SUBSTR(CAST(ev.parent_middleware_type_id
                                                   AS VARCHAR), 1, 8))
                                                               AS middleware_name,
             COALESCE(kd.kind, 'node_wrapper')                 AS kind,
             COALESCE(kd.band, 'node')                         AS band,
             COALESCE(ev.spatial_parent_node_id,
                      ln.node_id,
                      en.node_id)                              AS node_id,
             ev.action,
             ev.reason,
             ev.is_failure,
             ev.exception_message,
             -- It raised: it failed, and nothing it wrapped had already failed
             -- with the same exception.
             ev.is_failure AND NOT EXISTS (
               SELECT 1 FROM callee_failures cf
               WHERE cf.scope_id = ev.scope_id
                 AND cf.exception_message IS NOT DISTINCT FROM ev.exception_message
                 AND cf.timestamp <= ev.timestamp
             )                                                 AS raised_here
      FROM mw_events ev
      LEFT JOIN mw_llm_nodes ln
        ON ln.scope_id = ev.scope_id
       AND ln.llm_invoke_id = ev.spatial_parent_llm_invoke_id
      LEFT JOIN mw_enclosing en ON en.event_id = ev.event_id AND en.depth = 1
      LEFT JOIN mw_names nm ON nm.type_id = ev.parent_middleware_type_id
      LEFT JOIN mw_kinds kd ON kd.type_id = ev.parent_middleware_type_id
    )"""
    )


#: The per-group aggregate. Every middleware endpoint selects from this, so the
#: table, its pager total and its tiles cannot describe three different sets.
#:
#: ``invocations`` counts ``middleware.invocation`` specifically rather than all
#: events, because the generic invocation is the one event every middleware emits
#: exactly once per run — counting rows would make a guard (5 events per run)
#: look five times busier than a wrapper (2 per run) doing the same work.
#:
#: **``blocks`` is "it stopped the call", from either of the two ways that happens:**
#: a guard returning ``action = 'block'``, or any middleware raising an exception of
#: its own. Counting only the decisions missed the second — a `@wrap_node` that
#: raised was reported as having passed the call it killed.
#:
#: Counted over **distinct invocation ids**, not events: a guard that blocks emits
#: both a block decision *and* its own failure, so counting the events reported one
#: block as two.
#:
#: **``interruptions`` is the other side of that split** and replaces a plain count
#: of failures. A failure means the call did not complete through this middleware,
#: which for the 34-of-71 collateral failures says nothing about the middleware
#: itself: an exception unwinds through every enclosing layer. Keeping the two
#: counts apart is what stops every wrapper on a failed run from reading as a
#: blocker.
_MIDDLEWARE_GROUP_SELECT = """
    SELECT m.middleware_name,
           m.kind,
           m.band,
           COUNT(*) FILTER (WHERE m.event_type = 'middleware.invocation')
                                                              AS invocations,
           COUNT(*) FILTER (WHERE m.action IS NOT NULL)        AS decisions,
           COUNT(*) FILTER (WHERE m.action = 'allow')          AS allows,
           COUNT(*) FILTER (WHERE m.action = 'transform')      AS transforms,
           COUNT(DISTINCT m.invocation_key) FILTER (
             WHERE m.action = 'block' OR m.raised_here)        AS blocks,
           COUNT(DISTINCT m.invocation_key) FILTER (
             WHERE m.is_failure AND NOT m.raised_here)         AS interruptions,
           COUNT(DISTINCT m.session_id)                        AS sessions,
           COUNT(DISTINCT m.node_id)                           AS nodes,
           MIN(EPOCH(m.timestamp))                             AS first_seen,
           MAX(EPOCH(m.timestamp))                             AS last_seen,
           COALESCE(
             ARG_MAX(m.reason, m.timestamp) FILTER (
               WHERE m.action IN ('block', 'transform')),
             -- A middleware that raised has no decision to explain itself, so its
             -- own exception message is the reason it stopped the call.
             ARG_MAX(m.exception_message, m.timestamp) FILTER (WHERE m.raised_here)
           )                                                   AS reason
    FROM m
    LEFT JOIN sessions s ON s.scope_id = m.session_id
    LEFT JOIN nodes n ON n.scope_id = m.session_id AND n.node_id = m.node_id"""


def _middleware_filters(
    session_id: str | None = None,
    node_id: str | None = None,
    kinds: list[str] | None = None,
    bands: list[str] | None = None,
    middleware_names: list[str] | None = None,
    flow_names: list[str] | None = None,
    blocks_only: bool = False,
    include_internal: bool = False,
    since: float | None = None,
    until: float | None = None,
) -> tuple[str, str, list[Any]]:
    """Build the ``WHERE`` and ``HAVING`` the middleware endpoints share.

    Returns both because the two narrow at different grains and the split is not
    a choice: every filter here selects *events* except ``blocks_only``, which
    selects *groups* by a count over them. Expressing that as a ``WHERE`` would
    ask a different question — "invocations that blocked", which for a guard that
    blocked once in forty runs would keep one row and drop the other thirty-nine
    from its own totals. All three endpoints apply both clauses through this one
    function, so the tiles and the rows cannot disagree about which groups
    survive.

    ``since`` / ``until`` bound each *event's* own timestamp, so a middleware is
    in the window if it ran there. A group whose events straddle the boundary
    reports only the invocations inside it, which is the same convention the
    other list endpoints use and the reason the window is half-open.
    """
    predicates: list[str] = []
    params: list[Any] = []

    if session_id:
        predicates.append("m.session_id = ?")
        params.append(session_id)
    if node_id:
        predicates.append("m.node_id = ?")
        params.append(node_id)
    if kinds:
        predicates.append(_in_clause("m.kind", kinds))
        params.extend(kinds)
    if bands:
        predicates.append(_in_clause("m.band", bands))
        params.extend(bands)
    if middleware_names:
        predicates.append(_in_clause("m.middleware_name", middleware_names))
        params.extend(middleware_names)
    if flow_names:
        predicates.append(_in_clause("s.flow_name", flow_names))
        params.extend(flow_names)
    if not include_internal:
        predicates.append(
            f"m.middleware_name NOT IN ({', '.join('?' for _ in _INTERNAL_MIDDLEWARE_NAMES)})"
        )
        params.extend(_INTERNAL_MIDDLEWARE_NAMES)

    window, window_params = _window_predicates("EPOCH(m.timestamp)", since, until)
    predicates.extend(window)
    params.extend(window_params)

    where = "WHERE " + " AND ".join(predicates) if predicates else ""
    having = (
        "HAVING COUNT(*) FILTER (WHERE m.action = 'block') > 0" if blocks_only else ""
    )
    return where, having, params


def _middleware_groups_sql(where_clause: str, having_clause: str) -> str:
    """The grouped rows, as a subquery the three endpoints wrap differently.

    Shared rather than repeated so ``COUNT(*)`` over it, ``SUM()`` over it and the
    page of rows themselves are provably the same set — the listing pages it, the
    count counts it, the stats sum it.
    """
    return f"""
    WITH {_middleware_rows_cte()},
    {_SESSION_JOIN_CTE},
    {_NODE_JOIN_CTE.strip()}
    {_MIDDLEWARE_GROUP_SELECT}
    {where_clause}
    GROUP BY m.middleware_name, m.kind, m.band
    {having_clause}"""


def _middleware_order_clause(sort_by: MiddlewareSortField, order: SortOrder) -> str:
    """``ORDER BY`` for the middleware listing. See :func:`_order_clause`.

    ``(middleware_name, kind, band)`` is the unique final tiebreaker because it is
    the group key — nothing finer exists at this grain, and without it two
    middleware with equal invocation counts could swap between two queries and
    have a paging client see one twice.
    """
    tiebreakers = ["g.middleware_name ASC", "g.kind ASC", "g.band ASC"]
    return _order_clause(
        _MIDDLEWARE_SORT_COLUMNS[sort_by],
        order,
        tiebreakers,
    )


def count_middleware_rows(con: DuckDBPyConnection, **filters: Any) -> int:
    """Count middleware groups matching the filters, ignoring paging."""
    where_clause, having_clause, params = _middleware_filters(**filters)
    sql = f"""
    SELECT COUNT(*) AS total
    FROM ({_middleware_groups_sql(where_clause, having_clause)}) g
    """
    rows = _rows(con, sql, tuple(params), label="count_middleware_rows")
    return int(rows[0]["total"]) if rows else 0


def list_middleware_rows(
    con: DuckDBPyConnection,
    *,
    limit: int,
    offset: int,
    sort_by: MiddlewareSortField = MiddlewareSortField.INVOCATIONS,
    order: SortOrder = SortOrder.DESC,
    **filters: Any,
) -> list[dict[str, Any]]:
    """Return middleware rows with server-side filtering, sorting and paging."""
    where_clause, having_clause, params = _middleware_filters(**filters)
    order_clause = _middleware_order_clause(sort_by, order)
    sql = f"""
    SELECT g.*
    FROM ({_middleware_groups_sql(where_clause, having_clause)}) g
    {order_clause}
    LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])
    return _rows(
        con,
        sql,
        tuple(params),
        label=(
            f"list_middleware_rows(limit={limit}, offset={offset}, "
            f"sort={sort_by.value}:{order.value})"
        ),
    )


def get_middleware_stats(con: DuckDBPyConnection, **filters: Any) -> dict[str, Any]:
    """Roll-up across every middleware matching the filters, ignoring paging.

    ``total_middleware`` is the group count and ``total_invocations`` the sum of
    their invocations — the row count and the work behind it, which are different
    questions and so are different tiles.

    ``sessions`` is a ``MAX`` over the per-group distinct counts rather than a
    sum, because summing them would count one session once per middleware that
    ran in it. It is a floor on "sessions in view" rather than the exact figure,
    which is the honest thing available without a second pass over the events.
    """
    where_clause, having_clause, params = _middleware_filters(**filters)
    sql = f"""
    SELECT COUNT(*)                    AS total_middleware,
           COALESCE(SUM(g.invocations), 0) AS total_invocations,
           COALESCE(SUM(g.decisions), 0)   AS decisions,
           COALESCE(SUM(g.allows), 0)      AS allows,
           COALESCE(SUM(g.transforms), 0)  AS transforms,
           COALESCE(SUM(g.blocks), 0)      AS blocks,
           COALESCE(SUM(g.interruptions), 0) AS interruptions,
           COALESCE(MAX(g.sessions), 0)    AS sessions
    FROM ({_middleware_groups_sql(where_clause, having_clause)}) g
    """
    rows = _rows(con, sql, tuple(params), label="get_middleware_stats")
    return rows[0] if rows else {}


def list_middleware_filter_options(
    con: DuckDBPyConnection, include_internal: bool = False
) -> dict[str, list[str]]:
    """Distinct middleware names, kinds and bands across the whole stream.

    Computed over every middleware event rather than the current page, like the
    other filter-option endpoints: options drawn from the loaded rows could only
    ever offer what the active filter already matched.

    ``include_internal`` is threaded through so the dropdown cannot offer a name
    the default listing would then refuse to show.

    ``flow_names`` deliberately lists every flow in the stream, including ones
    that ran no middleware at all — the same choice the trace filters make, for
    the same reason: "this flow has no middleware" is a real answer.
    """
    internal_clause = (
        ""
        if include_internal
        else " WHERE middleware_name NOT IN ("
        + ", ".join("?" for _ in _INTERNAL_MIDDLEWARE_NAMES)
        + ")"
    )
    params: tuple[Any, ...] = (
        () if include_internal else tuple(_INTERNAL_MIDDLEWARE_NAMES)
    )

    group_rows = _rows(
        con,
        f"""
        WITH {_middleware_rows_cte()}
        SELECT DISTINCT middleware_name, kind, band
        FROM m{internal_clause}
        """,
        params,
        label="middleware_filter_options.groups",
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
        label="middleware_filter_options.flow_names",
    )

    #: Sorted by the enum's own declaration order rather than alphabetically, so
    #: the dropdown reads guards → transforms → wrappers the way the ladder does.
    kind_order = [k.value for k in MiddlewareKind]
    kinds = sorted(
        {r["kind"] for r in group_rows if r["kind"]},
        key=lambda k: kind_order.index(k) if k in kind_order else len(kind_order),
    )
    return {
        "middleware_names": sorted({r["middleware_name"] for r in group_rows}),
        "kinds": kinds,
        "bands": sorted({r["band"] for r in group_rows if r["band"]}),
        "flow_names": [r["flow_name"] for r in flow_rows],
    }


def list_middleware_by_session(
    con: DuckDBPyConnection, session_ids: Sequence[str]
) -> dict[str, list[dict[str, Any]]]:
    """Map ``session_id -> middleware that ran in it``, outermost first.

    Feeds the Agent Traces column. Takes the session ids the caller already holds
    rather than re-deriving the session filter, so the attached middleware is
    provably for exactly the rows being returned — a second copy of that
    predicate is the failure the shared-``WHERE`` discipline elsewhere in this
    module exists to prevent.

    Ordering is by each middleware's first ``middleware.invocation``, which *is*
    chain order: ``MiddlewareChain.run`` wraps in reversed order so index 0 is
    the outermost layer, and the outermost layer's invocation therefore fires
    first. ``MIN`` over all events rather than over the invocation alone, so a
    middleware that raised before emitting one still lands in position.

    Internal middleware is excluded unconditionally here. The column has no
    toggle — it is a fixed-width cell in a table of runs, where two glyphs that
    appear on every row would spend the width saying nothing.

    **The outcome is the worst thing this middleware did across the session, and
    the order of "worst" is deliberate:** blocked, then transformed, then
    interrupted, then passed. The first two are things the middleware *did*; the
    third is something that happened to it, so it ranks below them even though it
    is the more alarming word. A wrapper that an exception unwound through has not
    blocked anything, and colouring it as though it had would put a red pill on
    every layer of a failed run — which is the shape of the bug this replaces,
    where the shield beside these pills reported "all allowed" because the one
    decision that stopped the call had been dropped for lack of a node.
    """
    if not session_ids:
        return {}

    ids = list(session_ids)
    sql = f"""
    WITH {_middleware_rows_cte()}
    SELECT m.session_id,
           m.middleware_name,
           m.kind,
           m.band,
           CASE
             WHEN COUNT(*) FILTER (WHERE m.action = 'block'
                                      OR m.raised_here) > 0          THEN 'blocked'
             WHEN COUNT(*) FILTER (WHERE m.action = 'transform') > 0  THEN 'transformed'
             WHEN COUNT(*) FILTER (WHERE m.is_failure) > 0            THEN 'interrupted'
             ELSE 'passed'
           END                                                       AS outcome,
           COUNT(*) FILTER (WHERE m.event_type = 'middleware.invocation')
                                                                     AS invocations,
           COUNT(DISTINCT m.invocation_key) FILTER (
             WHERE m.action = 'block' OR m.raised_here)              AS blocks,
           COUNT(DISTINCT m.invocation_key) FILTER (
             WHERE m.is_failure AND NOT m.raised_here)               AS interruptions,
           COALESCE(
             ARG_MAX(m.reason, m.timestamp) FILTER (
               WHERE m.action IN ('block', 'transform')),
             ARG_MAX(m.exception_message, m.timestamp) FILTER (WHERE m.raised_here)
           )                                                         AS reason,
           MIN(m.timestamp)                                          AS first_at
    FROM m
    WHERE {_in_clause("m.session_id", ids)}
      AND m.middleware_name NOT IN
          ({", ".join("?" for _ in _INTERNAL_MIDDLEWARE_NAMES)})
    GROUP BY m.session_id, m.middleware_name, m.kind, m.band
    ORDER BY m.session_id, first_at ASC
    """
    rows = _rows(
        con,
        sql,
        (*ids, *_INTERNAL_MIDDLEWARE_NAMES),
        label=f"list_middleware_by_session({len(ids)} sessions)",
    )
    result: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        row.pop("first_at", None)
        result.setdefault(row.pop("session_id"), []).append(row)
    return result


# ---------------------------------------------------------------------------
# Guardrails per node
# ---------------------------------------------------------------------------


def list_guardrails_by_node(
    con: DuckDBPyConnection, session_id: str
) -> dict[str, list[dict[str, Any]]]:
    """Map ``node_id -> list of decision dicts`` for the session.

    A guard middleware event carries its decision under ``decision`` and its
    enclosing LLM invocation under ``spatial_parent_llm_invoke_id``; the LLM
    invocation in turn sits under a node (``llm.response.parent_llm_invoke_id``
    and ``spatial_parent_node_id``). We hop LLM → node to attribute every
    guardrail to a specific node.

    **That hop alone loses exactly the decisions that matter**, and it took a
    screenshot to notice: a guard that blocks does so *before* ``llm.invocation``
    fires, so its invocation has no ``llm.*`` events to hop through. Measured over
    104 decisions the hop resolved 91 and dropped 13 — and all 13 were blocks. So
    the tree's shield could report nothing but "allowed", while the Middleware
    column beside it correctly showed the call had been stopped. The fallback is
    :data:`_NODE_SPAN_CTE`: the innermost node invocation whose interval contains
    the decision. It recovers all 13 and agrees with the hop on 89 of the 89 where
    both resolve.

    **The rail's name comes from the middleware, not from the decision.** A
    ``GuardrailDecision`` carries ``action`` / ``reason`` / ``messages`` /
    ``output_message`` / ``user_facing_message`` / ``meta`` and has never had a
    name field, so reading one off it returned ``None`` on all 104 decisions in a
    3,887-event store — every row. That then tripped a fallback which assigned the
    whole decision blob to ``meta``, and the UI rendered a rail titled "Guardrail"
    above a JSON dump of its own decision.

    The name is one join away: the guard event's ``parent_middleware_type_id``
    names the middleware, and ``middleware.creation`` declares it. That join is
    global and grouped by the type_id, for the two reasons
    :func:`_middleware_rows_cte` gives — a creation event fires per process, and
    an ungrouped join fans each guard event out once per creation.

    ``meta`` is now the decision's own ``meta`` and nothing else.
    """
    sql = f"""
    WITH {_NODE_SPAN_CTE},
    guards AS (
      SELECT scope_id,
             event_type,
             CAST(spatial_parent_node_id AS VARCHAR)       AS direct_node_id,
             CAST(spatial_parent_llm_invoke_id AS VARCHAR) AS llm_invoke_id,
             CAST(parent_middleware_type_id AS VARCHAR)    AS type_id,
             CAST(decision AS VARCHAR)                     AS decision_json,
             timestamp
      FROM middleware
      WHERE scope_id = ?
        AND event_type IN (
          'middleware.guard.input.response',
          'middleware.guard.output.response'
        )
    ),
    llm_nodes AS (
      SELECT DISTINCT
             CAST(parent_llm_invoke_id AS VARCHAR)      AS llm_invoke_id,
             CAST(spatial_parent_node_id AS VARCHAR)    AS node_id
      FROM llm
      WHERE scope_id = ?
        AND event_type IN ('llm.invocation', 'llm.response')
    ),
    rail_names AS (
      -- Grouped by the join key, and deliberately not scoped to this session:
      -- see the docstring.
      SELECT CAST(middleware_type_id AS VARCHAR) AS type_id,
             ANY_VALUE(middleware_name)          AS middleware_name
      FROM middleware
      WHERE event_type = 'middleware.creation'
        AND middleware_type_id IS NOT NULL
      GROUP BY middleware_type_id
    ),
    -- The innermost node invocation open at the moment of the decision, ranked so
    -- `depth = 1` is the one a call stack would name. Only consulted when the hop
    -- above found nothing, which is the blocked case.
    enclosing AS (
      SELECT g.timestamp,
             g.type_id,
             s.node_id,
             ROW_NUMBER() OVER (
               PARTITION BY g.timestamp, g.type_id ORDER BY s.opened_at DESC
             ) AS depth
      FROM guards g
      JOIN node_spans s
        ON s.scope_id = g.scope_id
       AND g.timestamp >= s.opened_at
       AND (s.closed_at IS NULL OR g.timestamp <= s.closed_at)
    )
    SELECT COALESCE(g.direct_node_id, ln.node_id, e.node_id) AS node_id,
           g.event_type,
           g.decision_json,
           rn.middleware_name AS rail_name,
           g.timestamp
    FROM guards g
    LEFT JOIN llm_nodes ln USING (llm_invoke_id)
    LEFT JOIN rail_names rn USING (type_id)
    LEFT JOIN enclosing e
      ON e.timestamp = g.timestamp AND e.type_id IS NOT DISTINCT FROM g.type_id AND e.depth = 1
    ORDER BY g.timestamp ASC
    """
    result: dict[str, list[dict[str, Any]]] = {}
    guard_rows = _rows(
        con,
        sql,
        (session_id, session_id),
        label=f"list_guardrails_by_node({session_id[:8]})",
    )
    for row in guard_rows:
        node_id = row["node_id"]
        if not node_id:
            continue
        decision = _parse_json(row["decision_json"]) or {}
        if not isinstance(decision, dict):
            decision = {}
        phase = "input" if "input" in row["event_type"] else "output"
        meta = decision.get("meta")
        result.setdefault(node_id, []).append(
            {
                "rail_name": row["rail_name"],
                "phase": phase,
                "action": decision.get("action"),
                "reason": decision.get("reason"),
                "user_facing_message": decision.get("user_facing_message"),
                "meta": meta if isinstance(meta, dict) else None,
            }
        )
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_json(value: Any) -> Any:
    """Best-effort JSON decode of a value stored as text.

    Malformed JSON is logged and returned as the raw string rather than
    raised: a single corrupted payload should not blank out an entire
    listing. The warning is the only signal that something in the stream
    was written as invalid JSON — without it the client silently receives a
    string where a dict was promised.
    """
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError) as e:
            preview = value[:120] + ("…" if len(value) > 120 else "")
            print_warning(f"_parse_json: invalid JSON ({e}); returning raw string: {preview!r}")
            return value
    return value
