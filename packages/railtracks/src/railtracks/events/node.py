from __future__ import annotations

from dataclasses import dataclass
from traceback import format_exception
from typing import Any

from typing_extensions import Self

from railtracks.context.scope_link import ScopeLink
from railtracks.context.session_context import ScopeEntry
from railtracks.events._base import (
    CreationEventBase,
    FailureMixin,
    MiddlewareSpatialParent,
    NodeParent,
    NodeSpatialParent,
    ParentEventBase,
)
from railtracks.events._resolve import node_parent, node_spatial_parent
from railtracks.exceptions import FatalError, NodeInvocationError


def failure_details(exc: BaseException) -> dict[str, Any]:
    """The failure fields node events carry for an exception.

    `fatal` marks an exception that stops the whole run on its own; a run started with
    `end_on_error` stops on any failure.

    Args:
        exc: The exception the node raised.

    Returns:
        ``exception_name``, ``exception_message``, ``traceback``, and ``fatal``.
    """
    return {
        "exception_name": type(exc).__name__,
        "exception_message": str(exc),
        "traceback": "".join(format_exception(type(exc), exc, exc.__traceback__)),
        "fatal": isinstance(exc, FatalError)
        or (isinstance(exc, NodeInvocationError) and exc.fatal),
    }


@dataclass(kw_only=True)
class NodeEventBase(
    ParentEventBase[NodeSpatialParent | MiddlewareSpatialParent, NodeParent]
):
    def _get_spatial_parent(self, scope: ScopeLink[ScopeEntry] | None):
        return node_spatial_parent(scope)

    def _get_parent(self, scope: ScopeLink[ScopeEntry] | None):
        result = node_parent(scope)
        return result


@dataclass(kw_only=True)
class NodeCreation(CreationEventBase):
    """Node instantiated. Emitted before the node enters its own scope, so its parent
    resolves from the caller's ambient chain (no self-skip)."""

    node_id: str
    name: str
    node_type: str

    def event_type(self) -> str:
        return "node.creation"


@dataclass(kw_only=True)
class NodeInvocation(NodeEventBase):
    """Entering the node body."""

    args: tuple[Any, ...]
    kwargs: dict[str, Any]

    def event_type(self) -> str:
        return "node.invocation"


@dataclass(kw_only=True)
class NodeFailure(NodeEventBase, FailureMixin):
    """One run of the node's body raised. This is inside the node's middleware, which
    may still retry or recover; `node.destruction` carries the final outcome."""

    traceback: str = ""
    fatal: bool = False

    @classmethod
    def from_exception(cls, exc: Exception, **kwargs) -> Self:
        return cls(**failure_details(exc), **kwargs)

    def event_type(self) -> str:
        return "node.failure"


@dataclass(kw_only=True)
class NodeResponse(NodeEventBase):
    """The node's own response (inside its middleware)."""

    response: Any

    def event_type(self) -> str:
        return "node.response"


@dataclass(kw_only=True)
class NodeDestruction(NodeEventBase):
    """The node's final outcome, outside its middleware. The failure fields are set when
    the call raised and left None when it returned."""

    response: Any
    duration_seconds: float
    exception_name: str | None = None
    exception_message: str | None = None
    traceback: str | None = None
    fatal: bool = False

    def event_type(self) -> str:
        return "node.destruction"
