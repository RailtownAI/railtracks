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
        """Initialize the guardrail.

        Args:
            name: Rail name for traces and debugging; defaults to the class name.
        """
        self.name = name or self.__class__.__name__

    @abstractmethod
    def __call__(self, event: Any) -> GuardrailDecision:
        pass


class BaseLLMGuardrail(BaseGuardrail):
    """Abstract base class for guardrails that run on LLM input or output.

    Attributes:
        phase: Whether this rail expects :class:`LLMGuardrailPhase` ``INPUT`` or
            ``OUTPUT`` events.
    """

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
    """Base for guardrails that run on LLM input (e.g. prompt / message history).

    Attributes:
        phase: Always :attr:`LLMGuardrailPhase.INPUT`.
    """

    phase = LLMGuardrailPhase.INPUT

    def decide(
        self,
        input: str | Any | MessageHistory | LLMGuardrailEvent,
    ) -> GuardrailDecision:
        """Run this guard without building an :class:`LLMGuardrailEvent` by hand.

        Args:
            input: A :class:`LLMGuardrailEvent` (passed through), a ``str`` (treated
                as a single user message), a :class:`~railtracks.llm.message.Message`,
                or a :class:`~railtracks.llm.history.MessageHistory`.

        Returns:
            The :class:`GuardrailDecision` from :meth:`__call__`.

        Raises:
            TypeError: If ``input`` is not a ``str``, ``Message``, ``MessageHistory``,
                or :class:`LLMGuardrailEvent`.
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
    """Base for guardrails that run on LLM output (e.g. model response).

    Inspect ``event.output_message`` for the assistant message produced this turn.
    ``event.messages`` is conversation context and may not yet include that reply.

    Attributes:
        phase: Always :attr:`LLMGuardrailPhase.OUTPUT`.
    """

    phase = LLMGuardrailPhase.OUTPUT

    def decide(
        self,
        output: str | Any | MessageHistory | LLMGuardrailEvent,
    ) -> GuardrailDecision:
        """Run this guard without building an :class:`LLMGuardrailEvent` by hand.

        Args:
            output: A :class:`LLMGuardrailEvent` (passed through), a ``str`` (becomes
                the assistant message with empty prior history), a
                :class:`~railtracks.llm.message.Message`, or a non-empty
                :class:`~railtracks.llm.history.MessageHistory` (last message is the
                output under test; earlier entries become ``event.messages``).

        Returns:
            The :class:`GuardrailDecision` from :meth:`__call__`.

        Raises:
            ValueError: If ``output`` is an empty :class:`~railtracks.llm.history.MessageHistory`.
            TypeError: If ``output`` is not a ``str``, ``Message``, ``MessageHistory``,
                or :class:`LLMGuardrailEvent`.
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
                raise ValueError("Cannot decide with an empty MessageHistory.")
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
