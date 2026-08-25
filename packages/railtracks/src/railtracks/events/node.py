from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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
    """The final response, outside the node's middleware."""

    response: Any
    duration_seconds: float

    def event_type(self) -> str:
        return "node.destruction"
