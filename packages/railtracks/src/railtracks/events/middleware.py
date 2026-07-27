from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from railtracks.events._base import (
    UNSET,
    LLMSpatialParent,
    NodeSpatialParent,
    Parent,
    SessionEventBase,
    Unset,
)
from railtracks.guardrails.core.decision import GuardrailDecision
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import Message
from railtracks.llm.response import Response
from railtracks.llm.tools.tool import Tool


@dataclass(frozen=True)
class MiddlewareParent(Parent):
    middleware_id: str
    middleware_invoke_id: str


@dataclass(kw_only=True)
class MiddlewareCreationEvent:
    middleware_id: str
    middleware_name: str


@dataclass(kw_only=True)
class MiddlewareEventBase(SessionEventBase[NodeSpatialParent | LLMSpatialParent]):
    parent: MiddlewareParent | Unset = UNSET
    name: str

    def verify(self) -> None:
        super().verify()
        assert self.parent != UNSET, (
            "Parent ID should be resolved before publishing the event."
        )


@dataclass(kw_only=True)
class MiddlewareRegularEventBase(SessionEventBase[NodeSpatialParent]):
    pass


@dataclass(kw_only=True)
class MiddlewareModelEventBase(SessionEventBase[LLMSpatialParent]):
    pass


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
class MiddlewareGuardInputFailureEvent(MiddlewareModelEventBase):
    exception: Exception

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
class MiddlewareModelOutputFailureEvent(MiddlewareModelEventBase):
    exception: Exception

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
class MiddlewareOutputFailureEvent(MiddlewareRegularEventBase):
    exception: Exception

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
class MiddlewareGuardOutputFailureEvent(MiddlewareModelEventBase):
    exception: Exception

    def event_type(self) -> str:
        return "middleware.guard.output.failure"


# General middleware (invocation and response pair)
@dataclass(kw_only=True)
class MiddlewareInvocationEvent(MiddlewareEventBase):
    args: tuple[Any, ...]
    kwargs: dict[str, Any]

    def event_type(self) -> str:
        return "middleware.invocation"


@dataclass(kw_only=True)
class MiddlewareResponseEvent(MiddlewareEventBase):
    response: Any

    def event_type(self) -> str:
        return "middleware.response"


@dataclass(kw_only=True)
class MiddlewareFailureEvent(MiddlewareEventBase):
    exception: Exception

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
class MiddlewareModelFailureEvent(MiddlewareModelEventBase):
    exception: Exception

    def event_type(self) -> str:
        return "middleware.model.failure"
