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
    """

    #: Stable identifier for this call — the ``llm.response`` envelope id.
    trace_id: str
    session_id: str
    flow_id: str | None = None
    flow_name: str | None = None
    node_id: str
    node_name: str | None = None
    timestamp: float
    model_name: str | None = None
    model_provider: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost: float = 0.0
    #: Per-call latency reported by the provider, in seconds. Null when the
    #: provider did not report one.
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


TreeNode.model_rebuild()
