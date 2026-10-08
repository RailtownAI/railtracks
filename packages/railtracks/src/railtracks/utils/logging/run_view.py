"""Prints an indented, live view of each run from its session events.

Registered as an inline observability listener, so lines print in the order events are
emitted. What a run prints is fixed when it starts, from the logging level in effect in
the thread that started it (see ``enable_logging``).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from rich.text import Text

from railtracks.observability import Event

from .config import console, elapsed_text, run_view_level

_MAX_VALUE_CHARS = 120


@dataclass
class _Run:
    """What the view has learned about one running session."""

    level: int
    label: str
    end_on_error: bool
    # shared across runs: a model or middleware announces itself once per process
    models: dict[str, str]
    middleware_names: dict[str, str]
    node_names: dict[str, str] = field(default_factory=dict)
    depths: dict[str, int] = field(default_factory=dict)
    # LLM and middleware invoke ids -> the node they ran in
    owners: dict[str, str] = field(default_factory=dict)
    failed: set[str] = field(default_factory=set)
    # node id -> the node that called it (None for the entry point)
    parents: dict[str, str | None] = field(default_factory=dict)
    running: set[str] = field(default_factory=set)
    # nodes that ran alongside a sibling; their lines carry the branch name
    concurrent: set[str] = field(default_factory=set)


@dataclass
class _Line:
    level: int
    depth: int
    text: Text
    # the node to start from when looking for a concurrent branch to name
    within: str | None = None


class RunView:
    """Turns session events into console lines, keeping each session's state apart."""

    def __init__(self) -> None:
        self._runs: dict[str, _Run] = {}
        self._models: dict[str, str] = {}
        self._middleware_names: dict[str, str] = {}

    def record(self, event: Event) -> None:
        payload = event.payload
        if event.event_type == "llm.creation":
            self._models[payload["llm_id"]] = payload["model_name"]
        elif event.event_type == "middleware.creation":
            self._middleware_names[payload["middleware_type_id"]] = payload[
                "middleware_name"
            ]
        elif event.event_type == "session.started":
            level = run_view_level()
            if level is None:
                return
            self._runs[event.scope_id] = _Run(
                level=level,
                label=payload.get("flow_name")
                or payload.get("session_name")
                or payload.get("entry_point_name")
                or "run",
                end_on_error=bool(payload.get("end_on_error")),
                models=self._models,
                middleware_names=self._middleware_names,
            )

        run = self._runs.get(event.scope_id)
        if run is None:
            return

        _track(run, event)
        line = _render(run, event)
        if line is not None and line.level >= run.level:
            prefix = elapsed_text(event.stamp.timestamp())
            prefix.append("  " * line.depth)
            branch = _branch(run, line.within)
            if branch is not None:
                prefix.append(f"{_node_name(run, branch)} › ", "dim")
            console.print(prefix + line.text, soft_wrap=True)

        if event.event_type == "session.completed":
            self._runs.pop(event.scope_id, None)


def _track(run: _Run, event: Event) -> None:
    """Records the names and nesting that later lines need."""
    payload = event.payload
    event_type = event.event_type

    if event_type == "node.creation":
        run.node_names[payload["node_id"]] = payload["name"]
    elif event_type == "node.invocation":
        node_id = payload["parent_node_id"]
        caller = _caller(run, payload)
        run.depths[node_id] = run.depths.get(caller, 0) + 1 if caller else 1
        siblings = {n for n in run.running if run.parents.get(n) == caller}
        if siblings:
            run.concurrent.update(siblings)
            run.concurrent.add(node_id)
        run.parents[node_id] = caller
        run.running.add(node_id)
    elif event_type == "node.destruction":
        run.running.discard(payload["parent_node_id"])
    elif event_type == "node.failure":
        run.failed.add(payload["parent_node_id"])
    elif event_type.startswith("llm.") and event_type != "llm.creation":
        run.owners[payload["parent_llm_invoke_id"]] = payload["spatial_parent_node_id"]
    elif event_type.startswith("middleware.") and event_type != "middleware.creation":
        owner = _owner(run, payload)
        if owner is not None:
            run.owners[payload["parent_middleware_invoke_id"]] = owner


def _render(run: _Run, event: Event) -> _Line | None:
    event_type = event.event_type
    renderer = _RENDERERS.get(event_type)
    if renderer is not None:
        return renderer(run, event.payload)
    if event_type.startswith(("middleware.guard.", "middleware.verifier.")):
        return _render_middleware(run, event_type, event.payload)
    if event_type in _CONTEXT_OPERATIONS:
        text = Text(f"· {event_type} {', '.join(event.payload['keys'])}", "dim")
        return _Line(
            logging.DEBUG,
            _nested_depth(run, event.payload),
            text,
            _owner(run, event.payload),
        )
    return None


def _session_started(run: _Run, payload: dict[str, Any]) -> _Line:
    text = Text.assemble(
        (f"▶ {run.label}", "bold"),
        (f"  entry: {payload['entry_point_name']}", "dim"),
    )
    return _Line(logging.WARNING, 0, text)


def _session_completed(run: _Run, payload: dict[str, Any]) -> _Line:
    duration = f" in {payload['duration_seconds']:.3f}s"
    if payload["status"] == "failure":
        text = Text(f"✗ {run.label} failed{duration}: {payload['error']}", "bold red")
        return _Line(logging.ERROR, 0, text)
    return _Line(logging.WARNING, 0, Text(f"✓ {run.label}{duration}", "bold green"))


def _node_invocation(run: _Run, payload: dict[str, Any]) -> _Line:
    node_id = payload["parent_node_id"]
    text = Text(f"▶ {_node_name(run, node_id)}")
    if run.level <= logging.DEBUG:
        text.append(f" {_call_args(payload['args'], payload['kwargs'])}", "dim")
    return _Line(
        logging.INFO, run.depths.get(node_id, 1), text, run.parents.get(node_id)
    )


def _node_failure(run: _Run, payload: dict[str, Any]) -> _Line:
    node_id = payload["parent_node_id"]
    fatal = " (fatal)" if payload.get("fatal") or run.end_on_error else ""
    text = Text(
        f"✗ {_node_name(run, node_id)} failed: {_exception(payload)}{fatal}", "red"
    )
    return _Line(
        logging.ERROR, run.depths.get(node_id, 1), text, run.parents.get(node_id)
    )


def _node_destruction(run: _Run, payload: dict[str, Any]) -> _Line | None:
    """Fires whether the node succeeded or not; a failure already has its own line."""
    node_id = payload["parent_node_id"]
    if node_id in run.failed:
        return None
    text = Text.assemble(
        (f"✓ {_node_name(run, node_id)}", "green"),
        (f" {payload['duration_seconds']:.3f}s", "dim"),
    )
    if run.level <= logging.DEBUG:
        text.append(f" → {_truncate(repr(payload['response']))}", "dim")
    return _Line(
        logging.INFO, run.depths.get(node_id, 1), text, run.parents.get(node_id)
    )


def _llm_response(run: _Run, payload: dict[str, Any]) -> _Line:
    text = Text.assemble(
        (f"◆ {_model_name(run, payload)}", "cyan"), (_llm_stats(payload), "dim")
    )
    return _Line(logging.INFO, _nested_depth(run, payload), text, _owner(run, payload))


def _llm_failure(run: _Run, payload: dict[str, Any]) -> _Line:
    text = Text(f"✗ {_model_name(run, payload)} failed: {_exception(payload)}", "red")
    return _Line(logging.ERROR, _nested_depth(run, payload), text, _owner(run, payload))


_RENDERERS: dict[str, Callable[[_Run, dict[str, Any]], _Line | None]] = {
    "session.started": _session_started,
    "session.completed": _session_completed,
    "node.invocation": _node_invocation,
    "node.failure": _node_failure,
    "node.destruction": _node_destruction,
    "llm.response": _llm_response,
    "llm.failure": _llm_failure,
}

_CONTEXT_OPERATIONS = frozenset(
    {"context.get", "context.put", "context.update", "context.delete"}
)


def _render_middleware(
    run: _Run, event_type: str, payload: dict[str, Any]
) -> _Line | None:
    """What guardrails and verifiers decide, and when they raise themselves.

    Other middleware failure events only report the wrapped call's exception passing
    through, which the node or LLM line already shows.
    """
    name = run.middleware_names.get(payload["parent_middleware_type_id"], "middleware")
    depth = _nested_depth(run, payload)
    owner = _owner(run, payload)

    if event_type.endswith(".failure"):
        text = Text(f"✗ {name} failed: {_exception(payload)}", "red")
        return _Line(logging.ERROR, depth, text, owner)

    decision = payload.get("decision")
    if decision is None:
        return None
    action = getattr(decision.action, "value", decision.action)
    text = Text(f"· {name} → {action}", "magenta")
    if decision.reason:
        text.append(f" ({_truncate(decision.reason)})", "dim")
    return _Line(logging.DEBUG, depth, text, owner)


def _caller(run: _Run, payload: dict[str, Any]) -> str | None:
    """The node that called this one, through its middleware if need be; None for the
    entry point."""
    if payload.get("spatial_parent_type") == "middleware":
        return run.owners.get(payload["spatial_parent_middleware_invoke_id"])
    return payload.get("spatial_parent_node_id")


def _branch(run: _Run, node_id: str | None) -> str | None:
    """The nearest node at or above ``node_id`` that ran alongside a sibling.

    Indentation alone can't tell siblings' lines apart once they interleave, so lines
    inside such a branch are prefixed with its name.
    """
    while node_id is not None:
        if node_id in run.concurrent:
            return node_id
        node_id = run.parents.get(node_id)
    return None


def _owner(run: _Run, payload: dict[str, Any]) -> str | None:
    """The node an LLM, middleware, or context event happened in."""
    node_id = payload.get("spatial_parent_node_id")
    if node_id is not None:
        return node_id
    llm_invoke_id = payload.get("spatial_parent_llm_invoke_id")
    return run.owners.get(llm_invoke_id) if llm_invoke_id is not None else None


def _nested_depth(run: _Run, payload: dict[str, Any]) -> int:
    owner = _owner(run, payload)
    return run.depths.get(owner, 1) + 1 if owner is not None else 1


def _node_name(run: _Run, node_id: str) -> str:
    return run.node_names.get(node_id, node_id)


def _model_name(run: _Run, payload: dict[str, Any]) -> str:
    return (
        payload.get("reported_model_name")
        or run.models.get(payload.get("parent_llm_type_id"))
        or "LLM"
    )


def _llm_stats(payload: dict[str, Any]) -> str:
    stats = []
    if payload.get("input_tokens") is not None:
        stats.append(f"{payload['input_tokens']}→{payload['output_tokens']} tokens")
    if payload.get("total_cost") is not None:
        stats.append(f"${payload['total_cost']:.4f}")
    if payload.get("latency") is not None:
        stats.append(f"{payload['latency']:.2f}s")
    return f" {' · '.join(stats)}" if stats else ""


def _exception(payload: dict[str, Any]) -> str:
    return f"{payload['exception_name']}: {_truncate(payload['exception_message'])}"


def _call_args(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    parts = [repr(arg) for arg in args]
    parts.extend(f"{key}={value!r}" for key, value in kwargs.items())
    return _truncate(f"({', '.join(parts)})")


def _truncate(value: str) -> str:
    value = value.replace("\n", " ")
    if len(value) <= _MAX_VALUE_CHARS:
        return value
    return f"{value[: _MAX_VALUE_CHARS - 1]}…"
