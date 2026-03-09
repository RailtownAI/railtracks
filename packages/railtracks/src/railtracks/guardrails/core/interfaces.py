from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from .decision import GuardrailDecision
from .event import LLMGuardrailEvent, LLMGuardrailPhase


class LLMGuardrail(Protocol):
    """
    Protocol for LLM guardrails: callable with name and phase.

    Use this type when you need to accept any guardrail-like object (e.g. in APIs)
    without requiring a specific base class.
    """

    name: str
    phase: LLMGuardrailPhase

    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision: ...


class BaseLLMGuardrail(ABC):
    """Abstract base class for guardrails that run on LLM input or output."""

    phase: LLMGuardrailPhase
    name: str

    def __init__(self, name: str | None = None):
        self.name = name or self.__class__.__name__

    @abstractmethod
    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision:
        pass


class InputGuard(BaseLLMGuardrail):
    """Base for guardrails that run on LLM input (e.g. prompt / message history)."""

    phase = LLMGuardrailPhase.INPUT


class OutputGuard(BaseLLMGuardrail):
    """Base for guardrails that run on LLM output (e.g. model response)."""

    phase = LLMGuardrailPhase.OUTPUT
