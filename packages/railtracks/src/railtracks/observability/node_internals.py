"""Rebuilds the legacy session trace's per-node ``details.internals`` from events.

NOTE: This is a compatibility shim. When consumers read the event stream directly, this
and its wiring in ``Session.payload`` can be deleted together.
"""

from __future__ import annotations

from typing import Any

from .models import Event

_RELEVANT: frozenset[str] = frozenset(
    {
        "node.creation",
        "node.destruction",
        "llm.creation",
        "llm.invocation",
        "llm.response",
        "llm.failure",
        "middleware.creation",
        "middleware.guard.input.response",
        "middleware.guard.output.response",
        "middleware.guard.input.failure",
        "middleware.guard.output.failure",
    }
)

_GUARD_PHASES = {"input": "llm_input", "output": "llm_output"}

# The legacy key order within an internals block
_KEY_ORDER = ("guard_details", "llm_details", "latency")


class NodeInternalsCollector:
    """Collects session events and rebuilds ``details.internals`` per node.

    Registered as an *inline* listener rather than a ``Writer``: it holds no async
    state, and the session document needs every event, so a bounded queue with a
    drop policy would be the wrong mechanism. Going inline also keeps it clear of
    the Observer's per-writer consumer tasks, which bind to the loop that created
    them and misbehave across threads or a nested MCP server loop.

    :meth:`record` only buffers; the fold happens in :meth:`internals_for`, which
    keeps it independent of event ordering; guardrail events, for instance, arrive
    before the LLM event that says which node they belong to.

    State is keyed by session so a process running more than one keeps them apart.
    """

    def __init__(self) -> None:
        self._events: dict[str, list[Event]] = {}

    def record(self, event: Event) -> None:
        if event.event_type in _RELEVANT:
            self._events.setdefault(event.scope_id, []).append(event)

    def internals_for(self, session_id: str) -> dict[str, dict[str, Any]]:
        """The ``details.internals`` block for every node seen in this session.

        Keyed by node id, which is the same uuid the session document uses for
        ``runs[].nodes[].identifier``.
        """
        return _fold(self._events.get(session_id, []))

    def discard(self, session_id: str) -> None:
        """Drop a session's buffered events once its document has been written."""
        self._events.pop(session_id, None)


def _fold(events: list[Event]) -> dict[str, dict[str, Any]]:
    llm_owner = _llm_call_owners(events)
    models = _model_identities(events)
    middleware_names = {
        e.payload["middleware_type_id"]: e.payload["middleware_name"]
        for e in events
        if e.event_type == "middleware.creation"
    }

    internals: dict[str, dict[str, Any]] = {}

    for event in events:
        payload = event.payload
        event_type = event.event_type

        if event_type == "node.creation":
            entry = internals.setdefault(payload["node_id"], {})
            # An LLM node seeded both lists even when it made no calls, so an agent
            # that failed before its first request still reports empty lists.
            if payload.get("node_type") == "Agent":
                entry.setdefault("guard_details", [])
                entry.setdefault("llm_details", [])

        elif event_type == "node.destruction":
            # a node event's `parent` is the node itself; `spatial_parent` is its
            # caller, and is null for the entry point
            node_id = payload.get("parent_node_id")
            if node_id is not None:
                internals.setdefault(node_id, {})["latency"] = {
                    "total_time": payload["duration_seconds"]
                }

        elif event_type in ("llm.response", "llm.failure"):
            node_id = payload.get("spatial_parent_node_id")
            if node_id is not None:
                entry = internals.setdefault(node_id, {})
                entry.setdefault("llm_details", []).append(
                    _request_details(payload, models)
                )

        elif event_type.startswith("middleware.guard."):
            node_id = llm_owner.get(payload.get("spatial_parent_llm_invoke_id"))
            if node_id is not None:
                entry = internals.setdefault(node_id, {})
                entry.setdefault("guard_details", []).append(
                    _guard_trace(event_type, payload, middleware_names)
                )

    return {node_id: _ordered(block) for node_id, block in internals.items()}


def _llm_call_owners(events: list[Event]) -> dict[str, str]:
    """Map each LLM invocation id to the node that made the call.

    Guardrail events identify themselves by LLM invocation, not by node, so this is
    what lets their traces be attributed to a node.
    """
    owners: dict[str, str] = {}
    for event in events:
        if event.event_type not in ("llm.invocation", "llm.response", "llm.failure"):
            continue
        node_id = event.payload.get("spatial_parent_node_id")
        invoke_id = event.payload.get("parent_llm_invoke_id")
        if node_id is not None and invoke_id is not None:
            owners[invoke_id] = node_id
    return owners


def _model_identities(events: list[Event]) -> dict[str, tuple[str | None, str | None]]:
    """Map each model id to its ``(model_name, model_provider)``."""
    return {
        e.payload["llm_id"]: (
            e.payload.get("model_name"),
            e.payload.get("model_provider"),
        )
        for e in events
        if e.event_type == "llm.creation"
    }


def _request_details(
    payload: dict[str, Any], models: dict[str, tuple[str | None, str | None]]
) -> dict[str, Any]:
    """One ``llm_details`` entry, matching the legacy ``RequestDetails`` encoding.

    Message values are passed through as the raw objects the event carried; the
    session document's encoder renders them to the same shape the old one did.
    """
    model_name, model_provider = models.get(
        payload.get("parent_llm_type_id"), (None, None)
    )
    return {
        "model_name": payload.get("reported_model_name") or model_name,
        "model_provider": model_provider,
        "input": payload.get("message_input"),
        "output": payload.get("output"),
        "input_tokens": payload.get("input_tokens"),
        "output_tokens": payload.get("output_tokens"),
        "total_cost": payload.get("total_cost"),
        "system_fingerprint": payload.get("system_fingerprint"),
        "latency": payload.get("latency"),
    }


def _guard_trace(
    event_type: str, payload: dict[str, Any], middleware_names: dict[str, str]
) -> dict[str, Any]:
    """One ``guard_details`` entry, matching the legacy ``GuardrailTrace`` encoding.

    The rail's name is not on the event, so it is joined through the middleware that
    ran it; the phase comes from the event type.
    """
    phase = _GUARD_PHASES.get(event_type.split(".")[2], "")
    rail_name = middleware_names.get(payload.get("parent_middleware_type_id"), "")

    if event_type.endswith(".failure"):
        return {
            "rail_name": rail_name,
            "phase": phase,
            "action": "error",
            "reason": "Guardrail raised exception",
            "meta": {
                "exception_type": payload.get("exception_name"),
                "exception_message": payload.get("exception_message"),
            },
        }

    decision = payload.get("decision")
    return {
        "rail_name": rail_name,
        "phase": phase,
        "action": getattr(decision.action, "value", decision.action),
        "reason": decision.reason,
        "meta": decision.meta,
    }


def _ordered(block: dict[str, Any]) -> dict[str, Any]:
    return {key: block[key] for key in _KEY_ORDER if key in block}
