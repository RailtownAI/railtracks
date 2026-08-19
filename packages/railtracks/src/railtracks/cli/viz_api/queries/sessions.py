"""Session-summary queries.

The listing, the stats and the filter options all read the same
``_SESSION_SUMMARY_CTE`` through the same ``WHERE`` builder, so a stat tile
can never describe a different set of sessions than the table underneath it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ._common import _in_clause, _rows, _window_predicates

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection


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
