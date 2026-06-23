from __future__ import annotations

from railtracks.llm.history import MessageHistory
from railtracks.llm.message import Message

from .core import RTEvent


class LLMCallEvent(RTEvent):
    message_input: MessageHistory
    output: Message | None
    model_name: str | None
    model_provider: str | None
    input_tokens: int | None
    output_tokens: int | None
    total_cost: float | None
    latency: float | None
    success: bool
