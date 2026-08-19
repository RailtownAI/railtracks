"""Shared plumbing for the visualizer query modules.

The listing endpoints (sessions, LLM traces, events, middleware) are different
queries over different grains, but they narrow and order by the same rules —
an ``IN`` list built with the right number of placeholders, a half-open time
window, and an ordering that pages deterministically. These helpers exist so
each rule has one implementation. A second copy of any of them would
eventually disagree with the first, which is the failure the shared ``WHERE``
clause discipline elsewhere in this package exists to prevent.

The CTE constants below are the four denormalizing joins reused by multiple
modules — session flow, node name, node-invocation span, middleware name, and
LLM creation. Each is a self-contained CTE without punctuation; callers add
commas where they chain fragments.
"""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from ...io import print_warning
from .._debug import debug_print
from ..models import SortOrder

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection


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
        debug_print(f"  ↳ {label}: {len(rows)} row(s) in {elapsed_ms:.1f}ms")
    return rows


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
            print_warning(
                f"_parse_json: invalid JSON ({e}); returning raw string: {preview!r}"
            )
            return value
    return value


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

#: Model name/provider per (session, LLM), grouped by the join key so a
#: repeated ``llm.creation`` cannot fan a decorated row out. Shared by the
#: trace listing, the per-node totals, the details panel, and the model-name
#: filter option — callers filter by adding ``scope_id`` to the join.
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
