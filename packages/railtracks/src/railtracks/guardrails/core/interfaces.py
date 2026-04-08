from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol

from railtracks.llm.history import MessageHistory
from railtracks.llm.message import AssistantMessage, Message, UserMessage

from .decision import GuardrailDecision
from .event import LLMGuardrailEvent, LLMGuardrailPhase


class Guardrail(Protocol):
    """
    Base protocol for all guardrails: callable with a name.

    Concrete ABC hierarchies (e.g. :class:`BaseLLMGuardrail`) narrow the event
    type and add domain-specific attributes like ``phase``.
    """

    name: str

    def __call__(self, event: Any) -> GuardrailDecision: ...


class BaseGuardrail(ABC):
    """Abstract base class for all guardrails."""

    name: str

    def __init__(self, name: str | None = None):
        self.name = name or self.__class__.__name__

    @abstractmethod
    def __call__(self, event: Any) -> GuardrailDecision:
        pass


class BaseLLMGuardrail(BaseGuardrail):
    """Abstract base class for guardrails that run on LLM input or output."""

    phase: LLMGuardrailPhase

    @abstractmethod
    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision:
        pass


def _coerce_to_message_history(
    input: str | Any | MessageHistory,
) -> MessageHistory:
    """Convert str, Message, or MessageHistory to a MessageHistory."""
    if isinstance(input, MessageHistory):
        return input
    if isinstance(input, str):
        return MessageHistory([UserMessage(input)])
    if isinstance(input, Message):
        return MessageHistory([input])
    raise TypeError(
        f"Expected str, Message, MessageHistory, or LLMGuardrailEvent, "
        f"got {type(input).__name__}"
    )


class InputGuard(BaseLLMGuardrail):
    """Base for guardrails that run on LLM input (e.g. prompt / message history)."""

    phase = LLMGuardrailPhase.INPUT

    def evaluate(
        self,
        input: str | Any | MessageHistory | LLMGuardrailEvent,
    ) -> GuardrailDecision:
        """
        Convenience method to run the guardrail without constructing an
        ``LLMGuardrailEvent`` manually.

        Accepts ``str``, ``Message``, ``MessageHistory``, or a full
        ``LLMGuardrailEvent`` and delegates to ``__call__``.
        """
        if isinstance(input, LLMGuardrailEvent):
            return self(input)

        messages = _coerce_to_message_history(input)
        event = LLMGuardrailEvent(
            phase=LLMGuardrailPhase.INPUT,
            messages=messages,
        )
        return self(event)


class OutputGuard(BaseLLMGuardrail):
    """
    Base for guardrails that run on LLM output (e.g. model response).

    Inspect ``event.output_message`` for the assistant message produced this turn.
    ``event.messages`` is conversation context and may not yet include that reply.
    """

    phase = LLMGuardrailPhase.OUTPUT

    def evaluate(
        self,
        output: str | Any | MessageHistory | LLMGuardrailEvent,
    ) -> GuardrailDecision:
        """
        Convenience method to run the guardrail without constructing an
        ``LLMGuardrailEvent`` manually.

        Accepts ``str``, ``Message``, ``MessageHistory``, or a full
        ``LLMGuardrailEvent`` and delegates to ``__call__``.
        """
        if isinstance(output, LLMGuardrailEvent):
            return self(output)

        if isinstance(output, str):
            output_message = AssistantMessage(output)
            messages = MessageHistory()
        elif isinstance(output, Message):
            output_message = output
            messages = MessageHistory()
        elif isinstance(output, MessageHistory):
            if not output:
                raise ValueError("Cannot evaluate an empty MessageHistory.")
            output_message = output[-1]
            messages = MessageHistory(output[:-1])
        else:
            raise TypeError(
                f"Expected str, Message, MessageHistory, or LLMGuardrailEvent, "
                f"got {type(output).__name__}"
            )

        event = LLMGuardrailEvent(
            phase=LLMGuardrailPhase.OUTPUT,
            messages=messages,
            output_message=output_message,
        )
        return self(event)
