from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from railtracks.utils.deprecation import warn_pending_change

from . import llm
from .core import (
    GuardrailAction,
    GuardrailBlockedError,
    GuardrailDecision,
    GuardrailTrace,
    InputGuard,
    LLMGuardrailEvent,
    LLMGuardrailPhase,
    OutputGuard,
)

if TYPE_CHECKING:
    from .core.config import Guard as Guard
    from .core.interfaces import BaseGuardrail as BaseGuardrail
    from .core.interfaces import BaseLLMGuardrail as BaseLLMGuardrail
    from .core.interfaces import Guardrail as Guardrail

__all__ = [
    "GuardrailAction",
    "GuardrailBlockedError",
    "GuardrailDecision",
    "GuardrailTrace",
    "InputGuard",
    "OutputGuard",
    "LLMGuardrailEvent",
    "LLMGuardrailPhase",
    "llm",
]

_REMOVED: dict[str, str] = {
    "Guard": ".core.config",
    "Guardrail": ".core.interfaces",
    "BaseGuardrail": ".core.interfaces",
    "BaseLLMGuardrail": ".core.interfaces",
}


def __getattr__(name: str):
    if name in _REMOVED:
        warn_pending_change(
            f"rt.guardrails.{name}",
            change="is removed",
            detail=(
                "Guards attach as model middleware instead. Authoring is unchanged: "
                "InputGuard, OutputGuard and the decision types all stay."
            ),
        )
        module = importlib.import_module(_REMOVED[name], __name__)
        return getattr(module, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted([*__all__, *_REMOVED])
