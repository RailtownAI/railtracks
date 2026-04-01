from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict

from railtracks.llm import (
    MessageHistory,
)
from railtracks.llm.message import Message


class LLMGuardrailPhase(str, Enum):
    INPUT = "llm_input"
    OUTPUT = "llm_output"


class LLMGuardrailEvent(BaseModel):
    """
    Event passed to LLM guardrails.

    - ``messages``: conversation context (usually the history *before* the current
      assistant reply is appended to the node).
    - ``output_message``: for ``phase == OUTPUT``, the assistant ``Message`` being
      guarded this turn; ``None`` for INPUT phase or when not applicable.
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
