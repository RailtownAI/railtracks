from dataclasses import dataclass

from railtracks.context.scope_link import ScopeLink
from railtracks.context.session_context import ScopeEntry
from railtracks.events._resolve import llm_parent, llm_spatial_parent
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import Message
from railtracks.llm.providers import ModelProvider

from ._base import (
    CreationEventBase,
    LLMParent,
    NodeSpatialParent,
    ParentEventBase,
)


@dataclass(kw_only=True)
class LLMMessageBase(ParentEventBase[NodeSpatialParent, LLMParent]):
    message_input: MessageHistory

    def _get_spatial_parent(self, scope: ScopeLink[ScopeEntry] | None):
        return llm_spatial_parent(scope)

    def _get_parent(self, scope: ScopeLink[ScopeEntry] | None):
        return llm_parent(scope)


@dataclass(kw_only=True)
class LLMCreationEvent(CreationEventBase):
    model_id: str
    model_provider: ModelProvider
    model_name: str

    def event_type(self) -> str:
        return "llm.creation"


@dataclass(kw_only=True)
class LLMInvocationEvent(LLMMessageBase):
    def event_type(self) -> str:
        return "llm.invocation"


@dataclass(kw_only=True)
class LLMResponseEvent(LLMMessageBase):
    output: Message | None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_cost: float | None = None
    system_fingerprint: str | None = None
    latency: float | None = None

    def event_type(self) -> str:
        return "llm.response"


@dataclass(kw_only=True)
class LLMFailureEvent(LLMMessageBase):
    error_message: Exception

    def event_type(self) -> str:
        return "llm.failure"
