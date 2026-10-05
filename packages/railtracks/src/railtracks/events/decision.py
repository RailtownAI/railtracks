from dataclasses import dataclass
from typing import Any

from railtracks.context.scope_link import ScopeLink
from railtracks.context.session_context import ScopeEntry
from railtracks.events._resolve import enclosing_node_spatial_parent, node_parent

from ._base import FailureMixin, NodeParent, NodeSpatialParent, ParentEventBase


@dataclass(kw_only=True)
class DecisionEventBase(ParentEventBase[NodeSpatialParent, NodeParent]):
    """Base for events about one System One decision request.

    There is no decision scope, so the parent is the node the request ran inside, and
    ``decision_id`` pairs the invocation with its response or failure.
    """

    decision_id: str
    model_name: str

    def _get_spatial_parent(self, scope: ScopeLink[ScopeEntry] | None):
        return enclosing_node_spatial_parent(scope)

    def _get_parent(self, scope: ScopeLink[ScopeEntry] | None):
        return node_parent(scope)


@dataclass(kw_only=True)
class DecisionInvocationEvent(DecisionEventBase):
    """A decision request about to be sent; ``questions`` is the wire form."""

    api_base: str
    state: str | dict[str, Any] | list[Any]
    questions: dict[str, Any]

    def event_type(self) -> str:
        return "decision.invocation"


@dataclass(kw_only=True)
class DecisionResponseEvent(DecisionEventBase):
    """A completed decision request, plus what the provider reported about it."""

    reported_model_name: str | None
    provider: str | None
    answers: dict[str, Any]
    input_tokens: int | None
    output_tokens: int | None
    total_cost: float | None
    latency: float

    def event_type(self) -> str:
        return "decision.response"


@dataclass(kw_only=True)
class DecisionFailureEvent(DecisionEventBase, FailureMixin):
    def event_type(self) -> str:
        return "decision.failure"
