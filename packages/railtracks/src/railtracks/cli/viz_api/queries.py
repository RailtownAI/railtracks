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
from pathlib import Path
from typing import Any

from railtracks.query import EventQuery, connect

from ..io import print_status

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
    con,
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
       COALESCE(n.node_count, 0)                     AS node_count
FROM started s
LEFT JOIN completed c USING (scope_id)
LEFT JOIN llm_agg   l USING (scope_id)
LEFT JOIN node_agg  n USING (scope_id)
"""


def list_session_rows(con) -> list[dict[str, Any]]:
    return _rows(
        con,
        _SESSION_SUMMARY_CTE + "ORDER BY start_time DESC",
        label="list_session_rows",
    )


def get_session_row(con, session_id: str) -> dict[str, Any] | None:
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


def list_session_node_rows(con, session_id: str) -> list[dict[str, Any]]:
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


def list_llm_totals_by_node(con, session_id: str) -> list[dict[str, Any]]:
    """LLM cost/token roll-up per node, plus the model info of the final
    response for that node."""
    sql = """
    WITH resp AS (
      SELECT spatial_parent_node_id AS node_id,
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
    creations AS (
      -- Deduplicated per llm_id; a repeated llm.creation would otherwise
      -- duplicate the decorated row. Totals are aggregated above this join,
      -- so they were already correct — this keeps the row count honest too.
      SELECT llm_id, ANY_VALUE(model_provider) AS model_provider, ANY_VALUE(model_name) AS model_name
      FROM llm
      WHERE event_type = 'llm.creation' AND scope_id = ?
      GROUP BY llm_id
    ),
    last_resp AS (
      SELECT r.node_id,
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
    LEFT JOIN creations cr ON cr.llm_id = lr.parent_llm_type_id
    """
    return _rows(
        con,
        sql,
        (session_id, session_id),
        label=f"list_llm_totals_by_node({session_id[:8]})",
    )


# ---------------------------------------------------------------------------
# Node details — inputs / outputs
# ---------------------------------------------------------------------------


def get_node_row(con, session_id: str, node_id: str) -> dict[str, Any] | None:
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
    con, session_id: str, node_id: str
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """For an Agent node, return (final_response_row_or_none, totals_dict).

    The final row carries ``message_input`` and ``output`` for the details
    panel. Totals sum tokens/cost across every LLM response emitted from the
    node's scope.
    """
    sql = """
    WITH resp AS (
      SELECT timestamp,
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
    creations AS (
      -- Deduplicated per llm_id — see list_llm_totals_by_node.
      SELECT llm_id, ANY_VALUE(model_provider) AS model_provider, ANY_VALUE(model_name) AS model_name
      FROM llm
      WHERE event_type = 'llm.creation' AND scope_id = ?
      GROUP BY llm_id
    )
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
    LEFT JOIN creations cr ON cr.llm_id = r.parent_llm_type_id
    ORDER BY r.timestamp DESC
    LIMIT 1
    """
    rows = _rows(
        con,
        sql,
        (session_id, node_id, session_id),
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


def get_tool_io(con, session_id: str, node_id: str) -> dict[str, Any] | None:
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
# LLM traces — one row per llm.response, denormalized with session & node
# ---------------------------------------------------------------------------


def _trace_filters(
    session_id: str | None,
    node_id: str | None,
    flow_names: list[str] | None,
    model_names: list[str] | None,
) -> tuple[str, list[Any]]:
    """Build the shared ``WHERE`` clause for the trace queries.

    Both :func:`list_trace_rows` and :func:`count_trace_rows` go through here so
    a page and its total can never be computed over different predicates.
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
        placeholders = ", ".join("?" for _ in flow_names)
        predicates.append(f"s.flow_name IN ({placeholders})")
        params.extend(flow_names)
    if model_names:
        placeholders = ", ".join("?" for _ in model_names)
        predicates.append(
            f"COALESCE(r.reported_model_name, cr.model_name) IN ({placeholders})"
        )
        params.extend(model_names)

    return ("WHERE " + " AND ".join(predicates) if predicates else "", params)


def count_trace_rows(
    con,
    *,
    session_id: str | None = None,
    node_id: str | None = None,
    flow_names: list[str] | None = None,
    model_names: list[str] | None = None,
) -> int:
    """Count LLM-call rows matching the filters, ignoring paging.

    Selects no payload columns — the JSON blobs on ``message_input`` / ``output``
    are the expensive part of :func:`list_trace_rows`, and a count needs none
    of them.
    """
    where_clause, params = _trace_filters(session_id, node_id, flow_names, model_names)
    sql = f"""
    WITH llm_responses AS (
      SELECT event_id,
             scope_id,
             spatial_parent_node_id,
             parent_llm_type_id,
             reported_model_name
      FROM llm
      WHERE event_type = 'llm.response'
    ),
    creations AS (
      -- One row per (scope_id, llm_id). The stream can carry more than one
      -- llm.creation for the same llm_id, and without this the join below
      -- multiplies every response by however many creations it matched.
      SELECT scope_id, llm_id, ANY_VALUE(model_name) AS model_name
      FROM llm
      WHERE event_type = 'llm.creation'
      GROUP BY scope_id, llm_id
    ),
    sessions AS (
      SELECT scope_id, flow_name
      FROM session
      WHERE event_type = 'session.started'
    )
    SELECT COUNT(*) AS total
    FROM llm_responses r
    LEFT JOIN creations cr
      ON cr.scope_id = r.scope_id AND cr.llm_id = r.parent_llm_type_id
    LEFT JOIN sessions s
      ON s.scope_id = r.scope_id
    {where_clause}
    """
    rows = _rows(con, sql, tuple(params), label="count_trace_rows")
    return int(rows[0]["total"]) if rows else 0


def list_trace_rows(
    con,
    *,
    limit: int,
    offset: int,
    session_id: str | None = None,
    node_id: str | None = None,
    flow_names: list[str] | None = None,
    model_names: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Return LLM-call rows, newest first, with server-side filtering and paging.

    Denormalizes ``flow_name`` / ``flow_id`` from the session and ``node_name``
    from the node onto every row so the client can render, filter, and deep-link
    without a second lookup.
    """
    where_clause, params = _trace_filters(session_id, node_id, flow_names, model_names)

    sql = f"""
    WITH llm_responses AS (
      SELECT event_id,
             scope_id,
             spatial_parent_node_id,
             timestamp,
             parent_llm_type_id,
             message_input,
             output,
             input_tokens,
             output_tokens,
             total_cost,
             reported_model_name,
             latency
      FROM llm
      WHERE event_type = 'llm.response'
    ),
    creations AS (
      -- See count_trace_rows: deduplicated so a repeated llm.creation cannot
      -- fan a single response out into several trace rows.
      SELECT scope_id,
             llm_id,
             ANY_VALUE(model_provider) AS model_provider,
             ANY_VALUE(model_name)     AS model_name
      FROM llm
      WHERE event_type = 'llm.creation'
      GROUP BY scope_id, llm_id
    ),
    sessions AS (
      SELECT scope_id, flow_name, flow_id
      FROM session
      WHERE event_type = 'session.started'
    ),
    nodes AS (
      SELECT scope_id, node_id, name AS node_name
      FROM node
      WHERE event_type = 'node.creation'
    )
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
      COALESCE(r.input_tokens, 0)                    AS input_tokens,
      COALESCE(r.output_tokens, 0)                   AS output_tokens,
      COALESCE(r.total_cost, 0.0)                    AS total_cost,
      r.latency                                      AS latency_seconds,
      CAST(r.message_input AS VARCHAR)               AS message_input_json,
      CAST(r.output AS VARCHAR)                      AS output_json
    FROM llm_responses r
    LEFT JOIN creations cr
      ON cr.scope_id = r.scope_id AND cr.llm_id = r.parent_llm_type_id
    LEFT JOIN sessions s
      ON s.scope_id = r.scope_id
    LEFT JOIN nodes n
      ON n.scope_id = r.scope_id AND n.node_id = r.spatial_parent_node_id
    {where_clause}
    ORDER BY r.timestamp DESC
    LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])
    rows = _rows(
        con,
        sql,
        tuple(params),
        label=f"list_trace_rows(limit={limit}, offset={offset})",
    )
    for row in rows:
        row["inputs"] = _parse_json(row.pop("message_input_json"))
        row["output"] = _parse_json(row.pop("output_json"))
    return rows


# ---------------------------------------------------------------------------
# Guardrails per node
# ---------------------------------------------------------------------------


def list_guardrails_by_node(con, session_id: str) -> dict[str, list[dict[str, Any]]]:
    """Map ``node_id -> list of decision dicts`` for the session.

    A guard middleware event carries its decision under ``decision`` and its
    enclosing LLM invocation under ``spatial_parent_llm_invoke_id``; the LLM
    invocation in turn sits under a node (``llm.response.parent_llm_invoke_id``
    and ``spatial_parent_node_id``). We hop LLM → node to attribute every
    guardrail to a specific node.
    """
    sql = """
    WITH guards AS (
      SELECT event_type,
             CAST(spatial_parent_llm_invoke_id AS VARCHAR) AS llm_invoke_id,
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
    )
    SELECT ln.node_id,
           g.event_type,
           g.decision_json,
           g.timestamp
    FROM guards g
    LEFT JOIN llm_nodes ln USING (llm_invoke_id)
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
        phase = "input" if "input" in row["event_type"] else "output"
        result.setdefault(node_id, []).append(
            {
                "rail_name": decision.get("rail_name") or decision.get("name"),
                "phase": phase,
                "action": decision.get("action"),
                "reason": decision.get("reason"),
                "meta": decision
                if not isinstance(decision, dict) or "rail_name" not in decision
                else None,
            }
        )
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return value
    return value
