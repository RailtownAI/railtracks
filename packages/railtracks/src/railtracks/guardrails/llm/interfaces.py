from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Generic, ParamSpec, Protocol, TypeVar

from pydantic import BaseModel
from railtracks.context.central import get_parent_id, get_run_id, is_context_present
from railtracks.guardrails.core.trace import GuardrailTrace
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import AssistantMessage, Message, UserMessage
from railtracks.llm.response import Response
from railtracks.llm.tools.tool import Tool
from railtracks.middleware.core import Middleware

from ..core.decision import GuardrailDecision
from ..core.event import LLMGuardrailEvent, LLMGuardrailPhase

_P = ParamSpec("_P")
_R = TypeVar("_R")

class Guardrail(Protocol):
    """
    Base protocol for all guardrails: callable with a name.

    Concrete ABC hierarchies (e.g. :class:`BaseLLMGuardrail`) narrow the event
    type and add domain-specific attributes like ``phase``.
    """

    name: str

    def __call__(self, event: Any) -> GuardrailDecision: ...


class BaseGuardrail(ABC, Middleware[_P, _R], Generic[_P, _R]):
    """Abstract base class for all guardrails."""

    name: str

    def __init__(self, name: str | None = None):
        """Initialize the guardrail.

        Args:
            name: Rail name for traces and debugging; defaults to the class name.
        """
        self.name = name or self.__class__.__name__
        super().__init__(fn=self._middleware_fn)

    @abstractmethod
    async def _middleware_fn(
        cls,
        call: Callable[_P, Awaitable[_R]],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> _R:
        pass




