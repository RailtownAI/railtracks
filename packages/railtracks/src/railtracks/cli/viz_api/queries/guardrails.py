"""Guardrail decisions per node, for the session tree's shield markers.

A guard middleware event carries its decision under ``decision`` and its
enclosing LLM invocation under ``spatial_parent_llm_invoke_id``; the LLM
invocation in turn sits under a node (``llm.response.parent_llm_invoke_id``
and ``spatial_parent_node_id``). We hop LLM → node to attribute every
guardrail to a specific node, with :data:`_NODE_SPAN_CTE` as the fallback
for the block case (which fires before any ``llm.*`` event and so has
nothing to hop through).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ._common import _NODE_SPAN_CTE, _parse_json, _rows

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection


def list_guardrails_by_node(
    con: DuckDBPyConnection, session_id: str
) -> dict[str, list[dict[str, Any]]]:
    """Map ``node_id -> list of decision dicts`` for the session.

    **The LLM → node hop alone loses exactly the decisions that matter**, and it
    took a screenshot to notice: a guard that blocks does so *before*
    ``llm.invocation`` fires, so its invocation has no ``llm.*`` events to hop
    through. Measured over 104 decisions the hop resolved 91 and dropped 13 —
    and all 13 were blocks. So the tree's shield could report nothing but
    "allowed", while the Middleware column beside it correctly showed the call
    had been stopped. The fallback is :data:`_NODE_SPAN_CTE`: the innermost node
    invocation whose interval contains the decision. It recovers all 13 and
    agrees with the hop on 89 of the 89 where both resolve.

    **The rail's name comes from the middleware, not from the decision.** A
    ``GuardrailDecision`` carries ``action`` / ``reason`` / ``messages`` /
    ``output_message`` / ``user_facing_message`` / ``meta`` and has never had a
    name field, so reading one off it returned ``None`` on all 104 decisions in a
    3,887-event store — every row. That then tripped a fallback which assigned the
    whole decision blob to ``meta``, and the UI rendered a rail titled "Guardrail"
    above a JSON dump of its own decision.

    The name is one join away: the guard event's ``parent_middleware_type_id``
    names the middleware, and ``middleware.creation`` declares it. That join is
    global and grouped by the type_id, for the two reasons the middleware CTE
    documents — a creation event fires per process, and an ungrouped join fans
    each guard event out once per creation.

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
