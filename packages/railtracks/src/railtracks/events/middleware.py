from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from pydantic import BaseModel

from railtracks.events._base import (
    UNSET,
    CreationEventBase,
    FailureMixin,
    LLMAndMiddlewareSpatialParent,
    MiddlewareParent,
    NodeAndMiddlewareSpatialParent,
    ParentEventBase,
    Unset,
)
from railtracks.events._resolve import (
    middleware_parent,
    middleware_spatial_parent,
    model_middleware_spatial_parent,
    regular_middleware_spatial_parent,
)

if TYPE_CHECKING:
    from railtracks.guardrails.core.decision import GuardrailDecision
    from railtracks.llm.history import MessageHistory
    from railtracks.llm.message import Message
    from railtracks.llm.response import Response
    from railtracks.llm.tools.tool import Tool


@dataclass(kw_only=True)
class MiddlewareCreationEvent(CreationEventBase):
    middleware_type_id: str
    middleware_name: str

    def event_type(self) -> str:
        return "middleware.creation"


_T = TypeVar("_T", bound=NodeAndMiddlewareSpatialParent | LLMAndMiddlewareSpatialParent)


@dataclass(kw_only=True)
class MiddlewareEventBase(ParentEventBase[_T, MiddlewareParent], Generic[_T]):

    def verify(self) -> None:
        super().verify()
        assert self.parent != UNSET, (
            "Parent ID should be resolved before publishing the event."
        )

    def _get_parent(self, scope) -> MiddlewareParent:
        return middleware_parent(scope)


@dataclass(kw_only=True)
class MiddlewareRegularEventBase(MiddlewareEventBase[NodeAndMiddlewareSpatialParent]):
    def _get_spatial_parent(self, scope):
        return regular_middleware_spatial_parent(scope)


@dataclass(kw_only=True)
class MiddlewareModelEventBase(MiddlewareEventBase[LLMAndMiddlewareSpatialParent]):
    def _get_spatial_parent(self, scope):
        return model_middleware_spatial_parent(scope)


@dataclass(kw_only=True)
class MiddlewareGeneralEventBase(
    MiddlewareEventBase[NodeAndMiddlewareSpatialParent | LLMAndMiddlewareSpatialParent]
):
    def _get_spatial_parent(self, scope):
        result = middleware_spatial_parent(scope)

        return result


@dataclass(kw_only=True)
class MiddlewareModelInputTypesBase(MiddlewareModelEventBase):
    message_history: MessageHistory
    tools: list[Tool] | None
    schema: type[BaseModel] | None


@dataclass(kw_only=True)
class MiddlewareModelInputInvocationEvent(MiddlewareModelInputTypesBase):
    def event_type(self) -> str:
        return "middleware.model.input.invocation"


@dataclass(kw_only=True)
class MiddlewareModelInputResponseEvent(MiddlewareModelInputTypesBase):
    def event_type(self) -> str:
        return "middleware.model.input.response"


## Middleware Model Guardrails input (invocation and response)
@dataclass(kw_only=True)
class MiddlewareGuardInputInvocationEvent(MiddlewareModelEventBase):
    message_history: MessageHistory

    def event_type(self) -> str:
        return "middleware.guard.input.invocation"


@dataclass(kw_only=True)
class MiddlewareGuardInputResponseEvent(MiddlewareModelEventBase):
    decision: GuardrailDecision
    message_history: MessageHistory

    def event_type(self) -> str:
        return "middleware.guard.input.response"


@dataclass(kw_only=True)
class MiddlewareGuardInputFailureEvent(MiddlewareModelEventBase, FailureMixin):
    def event_type(self) -> str:
        return "middleware.guard.input.failure"


## Middleware Model output (invocation and response)
@dataclass(kw_only=True)
class MiddlewareModelOutputTypesBase(MiddlewareModelEventBase):
    response: Response


@dataclass(kw_only=True)
class MiddlewareModelOutputInvocationEvent(MiddlewareModelOutputTypesBase):
    def event_type(self) -> str:
        return "middleware.model.output.invocation"


@dataclass(kw_only=True)
class MiddlewareModelOutputResponseEvent(MiddlewareModelOutputTypesBase):
    def event_type(self) -> str:
        return "middleware.model.output.response"


@dataclass(kw_only=True)
class MiddlewareModelOutputFailureEvent(MiddlewareModelEventBase, FailureMixin):
    def event_type(self) -> str:
        return "middleware.model.output.failure"


## Middleware General output (invocation and response)
@dataclass(kw_only=True)
class MiddlewareOutputTypesBase(MiddlewareRegularEventBase):
    response: Any


@dataclass(kw_only=True)
class MiddlewareOutputInvocationEvent(MiddlewareOutputTypesBase):
    def event_type(self) -> str:
        return "middleware.regular.output.invocation"


@dataclass(kw_only=True)
class MiddlewareOutputResponseEvent(MiddlewareOutputTypesBase):
    def event_type(self) -> str:
        return "middleware.regular.output.response"


@dataclass(kw_only=True)
class MiddlewareOutputFailureEvent(MiddlewareRegularEventBase, FailureMixin):
    def event_type(self) -> str:
        return "middleware.regular.output.failure"


# Middleware model guardrails (invocation and response)
@dataclass(kw_only=True)
class MiddlewareGuardOutputInvocationEvent(MiddlewareModelEventBase):
    response: Message

    def event_type(self) -> str:
        return "middleware.guard.output.invocation"


@dataclass(kw_only=True)
class MiddlewareGuardOutputResponseEvent(MiddlewareModelEventBase):
    response: Message
    decision: GuardrailDecision

    def event_type(self) -> str:
        return "middleware.guard.output.response"


@dataclass(kw_only=True)
class MiddlewareGuardOutputFailureEvent(MiddlewareModelEventBase, FailureMixin):
    def event_type(self) -> str:
        return "middleware.guard.output.failure"


# General middleware (invocation and response pair)
@dataclass(kw_only=True)
class MiddlewareInvocationEvent(MiddlewareGeneralEventBase):
    args: tuple[Any, ...]
    kwargs: dict[str, Any]

    def event_type(self) -> str:
        return "middleware.invocation"


@dataclass(kw_only=True)
class MiddlewareResponseEvent(MiddlewareGeneralEventBase):
    response: Any

    def event_type(self) -> str:
        return "middleware.response"


@dataclass(kw_only=True)
class MiddlewareFailureEvent(MiddlewareGeneralEventBase, FailureMixin):
    def event_type(self) -> str:
        return "middleware.failure"


@dataclass(kw_only=True)
class MiddlewareModelInvocationEvent(MiddlewareModelEventBase):
    message_history: MessageHistory
    tools: list[Tool] | None
    schema: type[BaseModel] | None

    def event_type(self) -> str:
        return "middleware.model.invocation"


@dataclass(kw_only=True)
class MiddlewareModelResponseEvent(MiddlewareModelEventBase):
    response: Response

    def event_type(self) -> str:
        return "middleware.model.response"


@dataclass(kw_only=True)
class MiddlewareModelFailureEvent(MiddlewareModelEventBase, FailureMixin):
    def event_type(self) -> str:
        return "middleware.model.failure"
