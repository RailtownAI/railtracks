"""Middleware — one row per middleware, rolled up.

The grain here is a *middleware*, not one of its invocations: the question the
page answers ("which middleware ran, how often, and what did they block") is
about a set of invocations, so the set is the row. The per-invocation stream is
already served, at event grain, by ``/api/events?namespace=middleware``.

Three derivations happen here that the framework does not serve, and all three
are computed over the *whole* store rather than the filtered window, because
they are properties of the middleware rather than of the window. A window that
happened to exclude a guard's decision events would otherwise reclassify the
guard as a plain wrapper.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from ..models import (
    MiddlewareBand,
    MiddlewareKind,
    MiddlewareOutcome,
    MiddlewareSortField,
    SortOrder,
)
from ._common import (
    _MIDDLEWARE_NAME_CTE,
    _NODE_JOIN_CTE,
    _NODE_SPAN_CTE,
    _SESSION_JOIN_CTE,
    _in_clause,
    _order_clause,
    _rows,
    _window_predicates,
)

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection


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
#: Quoted SQL literals for the enum values, derived once so a rename in
#: ``models.py`` propagates into the SQL without a second edit.
_BAND_LLM_LITERAL = f"'{MiddlewareBand.LLM.value}'"
_BAND_NODE_LITERAL = f"'{MiddlewareBand.NODE.value}'"
_KIND_NODE_WRAPPER_LITERAL = f"'{MiddlewareKind.NODE_WRAPPER.value}'"
_OUTCOME_BLOCKED_LITERAL = f"'{MiddlewareOutcome.BLOCKED.value}'"
_OUTCOME_TRANSFORMED_LITERAL = f"'{MiddlewareOutcome.TRANSFORMED.value}'"
_OUTCOME_INTERRUPTED_LITERAL = f"'{MiddlewareOutcome.INTERRUPTED.value}'"
_OUTCOME_PASSED_LITERAL = f"'{MiddlewareOutcome.PASSED.value}'"

#: Event-pattern → kind, in precedence order. The SQL CASE below is generated
#: from this list so the enum values remain the single source of truth: rename
#: ``MiddlewareKind.INPUT_GUARD.value`` and the SQL updates with it.
_MIDDLEWARE_KIND_LADDER: list[tuple[str, MiddlewareKind]] = [
    ("event_type LIKE 'middleware.guard.input.%'", MiddlewareKind.INPUT_GUARD),
    ("event_type LIKE 'middleware.guard.output.%'", MiddlewareKind.OUTPUT_GUARD),
    ("event_type LIKE 'middleware.model.input.%'", MiddlewareKind.REQUEST_TRANSFORM),
    ("event_type LIKE 'middleware.model.output.%'", MiddlewareKind.RESPONSE_TRANSFORM),
    ("event_type LIKE 'middleware.regular.output.%'", MiddlewareKind.RESULT_HOOK),
    ("event_type LIKE 'middleware.model.%'", MiddlewareKind.LLM_WRAPPER),
    ("spatial_parent_type = 'llm_and_middleware'", MiddlewareKind.LLM_WRAPPER),
]

_MIDDLEWARE_KIND_CASE = (
    "\n      CASE\n"
    + "".join(
        f"        WHEN BOOL_OR({predicate}) THEN '{kind.value}'\n"
        for predicate, kind in _MIDDLEWARE_KIND_LADDER
    )
    + f"        ELSE {_KIND_NODE_WRAPPER_LITERAL}\n"
    + "      END"
)

#: SQL for each sortable measure, in terms of the grouped subquery's own columns.
#: Keyed by the enum, so nothing user-supplied reaches the ``ORDER BY``.
_MIDDLEWARE_SORT_COLUMNS = {
    MiddlewareSortField.INVOCATIONS: "g.invocations",
    MiddlewareSortField.BLOCKS: "g.blocks",
    MiddlewareSortField.NAME: "g.middleware_name",
    MiddlewareSortField.LAST_SEEN: "g.last_seen",
}

# One definition for the two ways middleware can stop an invocation. It is
# reused by the row aggregate, the blocks-only filter, and the per-session
# outcome so those surfaces cannot disagree.
_BLOCK_CONDITION = "m.action = 'block' OR m.raised_here"


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
        + f"""
    mw_kinds AS (
      SELECT parent_middleware_type_id           AS type_id,
             {_MIDDLEWARE_KIND_CASE}   AS kind,
             CASE WHEN BOOL_OR(spatial_parent_type = 'llm_and_middleware')
                  THEN {_BAND_LLM_LITERAL} ELSE {_BAND_NODE_LITERAL} END   AS band
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
             COALESCE(kd.kind, {_KIND_NODE_WRAPPER_LITERAL})   AS kind,
             COALESCE(kd.band, {_BAND_NODE_LITERAL})           AS band,
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
_MIDDLEWARE_GROUP_SELECT = f"""
    SELECT m.middleware_name,
           m.kind,
           m.band,
           COUNT(*) FILTER (WHERE m.event_type = 'middleware.invocation')
                                                              AS invocations,
           COUNT(*) FILTER (WHERE m.action IS NOT NULL)        AS decisions,
           COUNT(*) FILTER (WHERE m.action = 'allow')          AS allows,
           COUNT(*) FILTER (WHERE m.action = 'transform')      AS transforms,
           COUNT(DISTINCT m.invocation_key) FILTER (
             WHERE {_BLOCK_CONDITION})                         AS blocks,
           COUNT(DISTINCT m.invocation_key) FILTER (
             WHERE m.is_failure AND NOT m.raised_here)         AS interruptions,
           COUNT(DISTINCT m.session_id)                        AS sessions,
           LIST(DISTINCT m.session_id)                         AS session_ids,
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
    kinds: list[MiddlewareKind] | None = None,
    bands: list[MiddlewareBand] | None = None,
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
        # ``m.kind`` / ``m.band`` are the CASE ladder's own string values, so
        # bind each enum member's underlying value rather than the enum
        # instance itself — matches the ``LLMTraceStatus`` handling in
        # queries/llm_traces.py.
        params.extend(k.value for k in kinds)
    if bands:
        predicates.append(_in_clause("m.band", bands))
        params.extend(b.value for b in bands)
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
        f"HAVING COUNT(DISTINCT m.invocation_key) FILTER (WHERE {_BLOCK_CONDITION}) > 0"
        if blocks_only
        else ""
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

    ``sessions`` is the exact union of the session ids carried by the surviving
    groups. Summing the per-group counts would count a session once for every
    middleware that ran in it, while taking their maximum would under-count
    whenever different middleware ran in different sessions.
    """
    where_clause, having_clause, params = _middleware_filters(**filters)
    sql = f"""
    WITH grouped AS ({_middleware_groups_sql(where_clause, having_clause)}),
    totals AS (
      SELECT COUNT(*)                         AS total_middleware,
             COALESCE(SUM(invocations), 0)    AS total_invocations,
             COALESCE(SUM(decisions), 0)      AS decisions,
             COALESCE(SUM(allows), 0)         AS allows,
             COALESCE(SUM(transforms), 0)     AS transforms,
             COALESCE(SUM(blocks), 0)         AS blocks,
             COALESCE(SUM(interruptions), 0)  AS interruptions
      FROM grouped
    ),
    session_totals AS (
      SELECT COUNT(DISTINCT session_id) AS sessions
      FROM grouped, UNNEST(session_ids) AS ids(session_id)
    )
    SELECT totals.*, session_totals.sessions
    FROM totals CROSS JOIN session_totals
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
             WHEN COUNT(*) FILTER (WHERE {_BLOCK_CONDITION}) > 0   THEN {_OUTCOME_BLOCKED_LITERAL}
             WHEN COUNT(*) FILTER (WHERE m.action = 'transform') > 0  THEN {_OUTCOME_TRANSFORMED_LITERAL}
             WHEN COUNT(*) FILTER (WHERE m.is_failure) > 0            THEN {_OUTCOME_INTERRUPTED_LITERAL}
             ELSE {_OUTCOME_PASSED_LITERAL}
           END                                                       AS outcome,
           COUNT(*) FILTER (WHERE m.event_type = 'middleware.invocation')
                                                                     AS invocations,
           COUNT(DISTINCT m.invocation_key) FILTER (
             WHERE {_BLOCK_CONDITION})                                AS blocks,
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
