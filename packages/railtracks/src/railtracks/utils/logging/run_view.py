"""Prints an indented, live view of each run from its session events.

Registered as an inline observability listener, so lines print in the order events are
emitted. What a run prints is fixed when it starts, from the logging level in effect in
the thread that started it (see ``enable_logging``).
"""

from __future__ import annotations

import logging
import os
import re
import sysconfig
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from rich.text import Text

from railtracks.observability import Event

from .config import console, elapsed_text, run_view_level

_MAX_VALUE_CHARS = 120

# Frames from these are framework plumbing; a short traceback leaves them out
_RAILTRACKS_DIR = os.path.realpath(Path(__file__).parents[2])
_STDLIB_DIR = os.path.realpath(sysconfig.get_paths()["stdlib"])
_SITE_DIRS = tuple(
    os.path.realpath(sysconfig.get_paths()[key]) for key in ("purelib", "platlib")
)

# the file IPython compiles a notebook cell into
_NOTEBOOK_CELL = re.compile(r"ipykernel_\d+[/\\]\d+\.py$")


@dataclass
class _Node:
    """What the view knows about one node call, from the first time it is seen."""

    name: str
    # the node that called it; None for the entry point
    parent: str | None
    depth: int
    # ran alongside a sibling; lines inside it carry its name
    concurrent: bool = False
    # the failure of its latest attempt, until it runs again or ends
    attempt_failure: dict[str, Any] | None = None
    # the failed attempt that the current attempt is retrying
    retrying: dict[str, Any] | None = None


@dataclass
class _Run:
    """What the view has learned about one running session."""

    level: int
    label: str
    end_on_error: bool
    # only DEBUG prints user content: arguments, responses, and the run's result
    show_content: bool
    # shared across runs: a middleware announces itself once per process
    middleware_names: dict[str, str]
    # LLM id -> model name; a model announces itself before each call
    models: dict[str, str] = field(default_factory=dict)
    # node id -> name, from its creation until the node is first seen
    names: dict[str, str] = field(default_factory=dict)
    nodes: dict[str, _Node] = field(default_factory=dict)
    # ids of the nodes running right now
    running: set[str] = field(default_factory=set)
    # LLM and middleware invoke ids -> the node they ran in
    owners: dict[str, str] = field(default_factory=dict)
    # what the entry point returned, shown under the run's closing line
    result: str | None = None


@dataclass
class _Line:
    level: int
    depth: int
    text: Text
    # the node to start from when looking for a concurrent branch to name
    within: str | None = None
    # continuation lines printed under the text, such as a traceback
    detail: list[Text] = field(default_factory=list)


class RunView:
    """Turns session events into console lines, keeping each session's state apart."""

    def __init__(self) -> None:
        self._runs: dict[str, _Run] = {}
        self._middleware_names: dict[str, str] = {}

    def record(self, event: Event) -> None:
        payload = event.payload
        if event.event_type == "middleware.creation":
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
                show_content=level <= logging.DEBUG,
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
                prefix.append(f"{branch.name} › ", "dim")
            console.print(prefix + line.text, soft_wrap=True)
            pad = " " * (len(prefix.plain) + 2)
            for detail in line.detail:
                console.print(Text(pad) + detail, soft_wrap=True)

        if event.event_type == "session.completed":
            self._runs.pop(event.scope_id, None)


def _track(run: _Run, event: Event) -> None:
    """Records the names and nesting that later lines need."""
    payload = event.payload
    event_type = event.event_type

    if event_type == "node.creation":
        run.names[payload["node_id"]] = payload["name"]
    elif event_type.startswith("node."):
        _track_node(run, event_type, payload)
    elif event_type == "llm.creation":
        run.models[payload["llm_id"]] = payload["model_name"]
    elif event_type.startswith("llm."):
        run.owners[payload["parent_llm_invoke_id"]] = payload["spatial_parent_node_id"]
    elif event_type.startswith("middleware.") and event_type != "middleware.creation":
        owner = _owner(run, payload)
        if owner is not None:
            run.owners[payload["parent_middleware_invoke_id"]] = owner


def _track_node(run: _Run, event_type: str, payload: dict[str, Any]) -> None:
    node_id = payload["parent_node_id"]
    node = run.nodes.get(node_id)
    if node is None:
        # first sighting; usually the invocation, but a node whose middleware raises
        # before running it only shows up in its destruction
        node = run.nodes[node_id] = _place(run, node_id, payload)

    if event_type == "node.invocation":
        if node.attempt_failure is not None:
            node.retrying, node.attempt_failure = node.attempt_failure, None
        elif node_id not in run.running:
            _mark_concurrent_siblings(run, node)
        run.running.add(node_id)
    elif event_type == "node.failure":
        node.attempt_failure = payload
    elif event_type == "node.response":
        node.attempt_failure = None
    elif event_type == "node.destruction":
        if node.parent is None and payload["status"] == "success":
            run.result = _display(payload["response"])
        run.running.discard(node_id)
        node.attempt_failure = node.retrying = None


def _place(run: _Run, node_id: str, payload: dict[str, Any]) -> _Node:
    """The record for a node seen for the first time, nested under its caller."""
    parent = _caller(run, payload)
    caller = run.nodes.get(parent) if parent is not None else None
    return _Node(
        name=run.names.pop(node_id, node_id),
        parent=parent,
        depth=caller.depth + 1 if caller is not None else 1,
    )


def _mark_concurrent_siblings(run: _Run, node: _Node) -> None:
    """Marks ``node`` and its running siblings as concurrent, if any are running."""
    for sibling_id in run.running:
        sibling = run.nodes[sibling_id]
        if sibling.parent == node.parent:
            sibling.concurrent = node.concurrent = True


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
        return _Line(logging.CRITICAL if payload["fatal"] else logging.ERROR, 0, text)
    text = Text(f"✓ {run.label}{duration}", "bold green")
    detail = []
    if run.result is not None and run.show_content:
        detail.append(Text(f"→ {run.result}"))
    return _Line(logging.WARNING, 0, text, detail=detail)


def _node_invocation(run: _Run, payload: dict[str, Any]) -> _Line:
    node = run.nodes[payload["parent_node_id"]]
    if node.retrying is not None:
        text = Text(
            f"↻ {node.name} retrying after {_exception(node.retrying)}",
            "yellow",
        )
    else:
        text = Text(f"↳ {node.name}")
    if run.show_content:
        text.append(f" {_call_args(payload['args'], payload['kwargs'])}", "dim")
    return _Line(logging.INFO, node.depth, text, node.parent)


def _node_destruction(run: _Run, payload: dict[str, Any]) -> _Line:
    """The node's final outcome, after its middleware had its say."""
    node = run.nodes[payload["parent_node_id"]]
    if payload["status"] == "failure":
        fatal = payload["fatal"] or run.end_on_error
        text = Text(
            f"✗ {node.name} failed: {_exception(payload)}{' (fatal)' if fatal else ''}",
            "red",
        )
        detail = _traceback_lines(
            payload.get("frames") or [], full=run.level <= logging.DEBUG
        )
        return _Line(
            logging.CRITICAL if fatal else logging.ERROR,
            node.depth,
            text,
            node.parent,
            detail,
        )
    text = Text.assemble(
        (f"✓ {node.name}", "green"),
        (f" {payload['duration_seconds']:.3f}s", "dim"),
    )
    if run.show_content:
        text.append(f" → {_display(payload['response'])}", "dim")
    return _Line(logging.INFO, node.depth, text, node.parent)


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


def _branch(run: _Run, node_id: str | None) -> _Node | None:
    """The nearest node at or above ``node_id`` that ran alongside a sibling.

    Indentation alone can't tell siblings' lines apart once they interleave, so lines
    inside such a branch are prefixed with its name.
    """
    node = run.nodes.get(node_id) if node_id is not None else None
    while node is not None:
        if node.concurrent:
            return node
        node = run.nodes.get(node.parent) if node.parent is not None else None
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
    if owner is None:
        return 1
    node = run.nodes.get(owner)
    return (node.depth if node is not None else 1) + 1


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


def _traceback_lines(frames: list[dict[str, Any]], *, full: bool) -> list[Text]:
    """Where the exception was raised: each frame and its source line.

    Leaves out railtracks and standard-library frames unless ``full`` is set or nothing
    else is left.
    """
    if not full:
        frames = [
            frame for frame in frames if not _is_internal(frame["file"])
        ] or frames
    lines = []
    for frame in frames:
        location = f"{_display_path(frame['file'])}:{frame['line']}"
        lines.append(Text(f"{location} in {frame['function']}", "red"))
        if frame["source"]:
            lines.append(Text(f"  {frame['source']}", "red"))
    return lines


def _is_internal(path: str) -> bool:
    path = os.path.realpath(path)
    if _is_under(path, (_RAILTRACKS_DIR,)):
        return True
    return _is_under(path, (_STDLIB_DIR,)) and not _is_under(path, _SITE_DIRS)


def _is_under(path: str, directories: tuple[str, ...]) -> bool:
    return path.startswith(tuple(os.path.join(d, "") for d in directories))


def _display_path(path: str) -> str:
    """The path relative to the working directory when it is inside it."""
    if _NOTEBOOK_CELL.search(path):
        return "<cell>"
    try:
        relative = os.path.relpath(path)
    except ValueError:
        return path
    return path if relative.startswith("..") else relative


def _call_args(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    parts = [repr(arg) for arg in args]
    parts.extend(f"{key}={value!r}" for key, value in kwargs.items())
    return _truncate(f"({', '.join(parts)})")


def _display(value: Any) -> str:
    """A value as one short line; ``str`` so an agent's response shows its content."""
    return _truncate(str(value))


def _truncate(value: str) -> str:
    value = value.replace("\n", " ")
    if len(value) <= _MAX_VALUE_CHARS:
        return value
    return f"{value[: _MAX_VALUE_CHARS - 1]}…"
