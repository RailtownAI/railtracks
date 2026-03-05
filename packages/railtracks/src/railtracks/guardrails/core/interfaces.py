from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from .decision import GuardrailDecision
from .event import LLMGuardrailEvent, LLMGuardrailPhase


class LLMGuardrail(Protocol):
    name: str
    phase: LLMGuardrailPhase

    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision: ...


class BaseLLMGuardrail(ABC):
    phase: LLMGuardrailPhase
    name: str

    def __init__(self, name: str | None = None):
        self.name = name or self.__class__.__name__

    @abstractmethod
    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision:
        pass


class InputGuard(BaseLLMGuardrail):
    phase = LLMGuardrailPhase.INPUT


class OutputGuard(BaseLLMGuardrail):
    phase = LLMGuardrailPhase.OUTPUT
