"""Pydantic response models for the Railtracks visualizer HTTP API.

These are the contract between the FastAPI server in ``viz_server.py`` and the
`@railtownai/railtracks-visualizer` SPA. They are shaped for the event-stream
data model (one ``session.jsonl`` under the events home, queried via DuckDB) —
no ``runs`` array, no server-computed timeline steps, no migration shims for the
old JSON-tree renderer.

Timestamps are unix **seconds** (float). Durations are also seconds.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    """Rolled-up status for a session."""

    COMPLETED = "Completed"
    FAILED = "Failed"
    RUNNING = "Running"


class NodeStatus(str, Enum):
    """Terminal state of a single node.

    Lowercase, unlike :class:`SessionStatus`, because these values were already
    being emitted on ``GraphNode.status`` before this enum existed and the
    React Flow node renderers switch on them verbatim.
    """

    SUCCESS = "success"
    FAILURE = "failure"
    RUNNING = "running"


class TraceSortField(str, Enum):
    """Sortable columns on ``GET /api/traces``.

    Names are the user-facing measure, not the storage column: ``tokens`` sorts
    on input + output combined, because that is the number the table renders as
    one cell.
    """

    TIMESTAMP = "timestamp"
    COST = "cost"
    TOKENS = "tokens"
    LATENCY = "latency"


class TraceStatus(str, Enum):
    """How one LLM round trip ended.

    Lowercase like :class:`NodeStatus` and unlike :class:`SessionStatus`, and
    the vocabulary is the call's own rather than the run's: a call that raised
    did not "fail to complete a run", it returned an error — which is what the
    row then carries, under ``error_name`` / ``error_message``.
    """

    SUCCESS = "success"
    ERROR = "error"


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class LLMContent(BaseModel):
    """One message in an LLM exchange. ``content`` is deliberately untyped: it
    may be a string, a tool-call list, a tool response, or arbitrary JSON."""

    role: str
    content: Any = None


class Guardrail(BaseModel):
    """A single guardrail decision, surfaced from ``middleware.guard.*`` events."""

    rail_name: str | None = None
    phase: str
    action: str | None = None
    reason: str | None = None
    meta: dict[str, Any] | None = None


class SessionSummary(BaseModel):
    """One row of the sessions table. No graph data."""

    session_id: str
    #: Resolved display name. Fallback chain: flow_name -> session_name -> entry_point_name -> "".
    name: str
    flow_id: str | None = None
    flow_name: str | None = None
    entry_point_name: str | None = None
    start_time: float
    end_time: float | None = None
    #: ``session.completed.duration_seconds`` when completed, else ``end_time - start_time``.
    duration: float | None = None
    status: SessionStatus
    total_cost: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    node_count: int = 0


class NodeRef(BaseModel):
    node_id: str


class TreeNode(BaseModel):
    """A node in the session tree, already parented and sorted."""

    node_id: str
    display_name: str
    #: "Agent" | "Tool".
    node_type: str
    latency_seconds: float = 0.0
    failed: bool = False
    guardrails: list[Guardrail] = Field(default_factory=list)
    children: list[TreeNode] = Field(default_factory=list)


class SessionDetail(SessionSummary):
    """Full session payload for the drawer.

    ``default_selection`` is the node the drawer auto-selects on open — the
    tree's first root, or ``None`` for a session with no Agent/Tool nodes.
    """

    tree: list[TreeNode] = Field(default_factory=list)
    default_selection: NodeRef | None = None


class NodeDetail(BaseModel):
    """Everything the node details panel renders for one selected node."""

    node_id: str
    node_type: str
    name: str
    #: Matches ``GraphNode.status`` for the same node. Present so the details
    #: panel can tag a failed response without consulting the session tree —
    #: the on-canvas inspector has no tree to consult.
    status: NodeStatus = NodeStatus.SUCCESS
    inputs: list[LLMContent] = Field(default_factory=list)
    #: Agent nodes: the final LLM reply. None for Tool nodes.
    output: LLMContent | None = None
    #: Tool nodes: the raw tool return value. None for Agent nodes.
    tool_output: Any = None
    model_name: str | None = None
    model_provider: str | None = None
    total_cost: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    guardrails: list[Guardrail] = Field(default_factory=list)
    latency_seconds: float | None = None


class GraphNode(BaseModel):
    """A node in the React Flow graph, with its per-node stats precomputed."""

    id: str
    #: "Agent" | "Tool"; unrecognised types pass through unchanged.
    type: str
    label: str
    time: float | None = None
    model_name: str | None = None
    model_provider: str | None = None
    total_cost: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    latency_seconds: float | None = None
    #: "success" | "failure" | "running".
    status: str | None = None
    guardrails: list[Guardrail] = Field(default_factory=list)


class GraphEdge(BaseModel):
    """A parent → child edge in the React Flow graph.

    Root nodes appear with ``source = None`` so the SPA can filter or draw an
    entry marker at its discretion.
    """

    id: str
    source: str | None = None
    target: str


class SessionGraph(BaseModel):
    """Full graph for one session."""

    session_id: str
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class TraceRow(BaseModel):
    """One LLM call, denormalized with session and node context.

    Feeds the LLM Traces tab (cross-session listing) and, when queried with a
    ``node_id`` filter, the per-call breakdown for one node.

    A row is one round trip, ended or raised: ``llm.response`` and
    ``llm.failure`` both produce one. A call that raised was invisible here
    until it did — the request that broke a run was the one thing the traces
    could not show, and a looping agent's failed turn read as a turn that never
    happened.

    On an error row the provider reported no usage, so ``input_tokens``,
    ``output_tokens`` and ``total_cost`` are zero and ``output`` is null.
    ``inputs`` is still the message history that was sent, which is the point:
    it is what you look at to see what broke. ``latency_seconds`` stays null
    rather than being filled from the wall clock — the successful rows carry a
    provider-reported figure, and two different measures in one column would
    make its sort meaningless.
    """

    #: Stable identifier for this call — the ``llm.response`` / ``llm.failure``
    #: envelope id.
    trace_id: str
    session_id: str
    flow_id: str | None = None
    flow_name: str | None = None
    node_id: str
    node_name: str | None = None
    timestamp: float
    model_name: str | None = None
    model_provider: str | None = None
    #: How the round trip ended. Older clients that ignore it still read every
    #: other field correctly; the zeros on an error row are honest.
    status: TraceStatus = TraceStatus.SUCCESS
    #: Exception type, e.g. ``AuthenticationError``. Null unless ``status`` is
    #: ``error``.
    error_name: str | None = None
    error_message: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost: float = 0.0
    #: Per-call latency reported by the provider, in seconds. Null when the
    #: provider did not report one, and always null on an error row.
    latency_seconds: float | None = None
    inputs: list[LLMContent] = Field(default_factory=list)
    output: LLMContent | None = None


class TracePage(BaseModel):
    """One page of :class:`TraceRow`, with the unpaged total alongside it.

    An envelope rather than a bare list plus an ``X-Total-Count`` header: the
    server ships no CORS middleware, so a custom header is invisible to any
    client on another origin (the Electron shell points at
    ``VITE_API_ORIGIN``). The count also lets a client render "1-50 of 412"
    without asking for ``page_size + 1`` rows to probe for a next page.
    """

    #: Rows matching the filters, after ``limit`` / ``offset``.
    rows: list[TraceRow] = Field(default_factory=list)
    #: Rows matching the filters, ignoring ``limit`` / ``offset``.
    total: int = 0
    limit: int = 0
    offset: int = 0


class SessionStats(BaseModel):
    """Roll-up across every session matching the filters.

    Computed server-side and over the whole filtered set, not the rows a client
    happens to hold. Summing in the browser would re-derive what the server
    already knows, and would start lying the day the sessions list is paginated.

    ``successes + failures + running == total_runs``; the three statuses are
    exhaustive because the roll-up has no fourth outcome.
    """

    total_runs: int = 0
    successes: int = 0
    failures: int = 0
    running: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost: float = 0.0


class SessionFilterOptions(BaseModel):
    """Values the session filters accept, across every session in the stream."""

    flow_names: list[str] = Field(default_factory=list)
    entry_point_names: list[str] = Field(default_factory=list)
    #: Rolled-up status values — "Completed" | "Failed" | "Running".
    statuses: list[str] = Field(default_factory=list)


class TraceStats(BaseModel):
    """Roll-up across every LLM call matching the trace filters.

    Counts exactly the calls the traces table can show, which now includes the
    ones that raised: ``total_calls`` covers ``llm.response`` and
    ``llm.failure`` alike, and ``failed_calls`` breaks out the second group.
    The two must move together — a tile counting a set the table cannot list
    (or listing rows the tile does not count) contradicts the rows underneath
    it the moment a filter is touched.

    Tokens and cost are unaffected by the addition: an error row reports no
    usage and contributes zero to both. ``AVG`` and ``MAX`` skip nulls, so an
    error's null latency neither lowers the average nor counts toward it.
    """

    total_calls: int = 0
    #: Calls that raised. ``total_calls - failed_calls`` is the number that
    #: returned a response.
    failed_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost: float = 0.0
    #: Null when nothing matching reported a latency.
    avg_latency_seconds: float | None = None
    max_latency_seconds: float | None = None


class TraceFilterOptions(BaseModel):
    """Every value the ``/api/traces`` filters can usefully take.

    Computed over the whole event stream rather than the current page, so a
    dropdown offers what the *data* holds and not what the last query happened
    to return. The lists are independent of each other and of any active filter
    — narrowing them per selection would make a chosen value vanish from its own
    dropdown.

    ``node_names`` and ``model_names`` come from nodes and models that actually
    made an LLM call — responses *and* failures, so an agent whose only call
    raised is still offered rather than being filtered out of its own error.
    A Tool node can never appear in the traces table, so offering it would only
    promise empty results. ``flow_names`` deliberately lists *every* flow,
    including ones that made no LLM calls — "this flow made no calls" is a real
    answer to a real question.

    There is no ``statuses`` list to match :class:`SessionFilterOptions`: a
    session's status is a SQL ``CASE`` over the stream and has to be discovered
    from it, where a trace's is the two-valued :class:`TraceStatus` the contract
    already names. "No calls failed" is also a useful thing for that filter to
    report, which an options list computed from the data could never say.
    """

    flow_names: list[str] = Field(default_factory=list)
    #: Agent node names, as rendered in the table's Agent column.
    node_names: list[str] = Field(default_factory=list)
    model_names: list[str] = Field(default_factory=list)


TreeNode.model_rebuild()
