from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol

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


class InputGuard(BaseLLMGuardrail):
    """Base for guardrails that run on LLM input (e.g. prompt / message history)."""

    phase = LLMGuardrailPhase.INPUT


class OutputGuard(BaseLLMGuardrail):
    """
    Base for guardrails that run on LLM output (e.g. model response).

    Inspect ``event.output_message`` for the assistant message produced this turn.
    ``event.messages`` is conversation context and may not yet include that reply.
    """

    phase = LLMGuardrailPhase.OUTPUT
