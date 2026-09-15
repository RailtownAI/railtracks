"""Node-level queries within a session.

These feed the session detail drawer and the graph endpoint: the per-node
rows for the tree, the LLM cost/token roll-up per node, and the input/output
payloads for the node details panel.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ._common import _LLM_CREATION_JOIN_CTE, _parse_json, _rows

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection


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
