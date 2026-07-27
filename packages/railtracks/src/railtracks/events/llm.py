from railtracks.llm.history import MessageHistory
from railtracks.llm.message import Message
from railtracks.llm.providers import ModelProvider

from ._base import UNSET, NoSpatialParent, NodeSpatialParent, Parent, SessionEventBase, Unset

from dataclasses import dataclass

@dataclass(frozen=True)
class LLMParent(Parent):
    llm_model_id: str
    llm_invoke_id: str

@dataclass(kw_only=True)
class LLMMessageBase(SessionEventBase[NodeSpatialParent]):
    message_input: MessageHistory
    parent: LLMParent | Unset = UNSET

    def verify(self) -> None:
        super().verify()
        assert self.parent != UNSET, (
            "Parent ID should be resolved before publishing the event."
        )

@dataclass(kw_only=True)
class LLMCreationEvent(SessionEventBase[NoSpatialParent]):
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


