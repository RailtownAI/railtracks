from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict

from railtracks.llm import (
    MessageHistory,
)
from railtracks.llm.message import Message


class LLMGuardrailPhase(str, Enum):
    """Which side of the LLM call a guardrail observes.

    Members:
        INPUT: Before the model (prompt / history), value ``llm_input``.
        OUTPUT: After the model (assistant message), value ``llm_output``.
    """

    INPUT = "llm_input"
    OUTPUT = "llm_output"


class LLMGuardrailEvent(BaseModel):
    """Payload for LLM input and output guardrails.

    Attributes:
        phase: Whether this is an input-phase or output-phase check.
        messages: Conversation context, usually the history before the current
            assistant reply is appended by the node.
        output_message: For ``OUTPUT`` phase, the assistant :class:`~railtracks.llm.message.Message`
            under inspection; ``None`` for input phase or when not applicable.
        node_name: Optional node label for observability.
        node_uuid: Optional stable node id for observability.
        run_id: Optional run correlation id.
        model_name: Optional resolved model name for observability.
        model_provider: Optional provider string for observability.
        tags: Optional key/value metadata (e.g. ``agent_kind`` from the mixin).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    phase: LLMGuardrailPhase
    messages: MessageHistory
    output_message: Message | None = None

    node_name: str | None = None
    node_uuid: str | None = None
    run_id: str | None = None
    model_name: str | None = None
    model_provider: str | None = None
    tags: dict[str, str] | None = None
