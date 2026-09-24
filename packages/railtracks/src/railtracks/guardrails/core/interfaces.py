from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Generic, ParamSpec, Protocol, TypeVar

from railtracks.middleware.core import Middleware, _MiddlewareSignature

from .decision import GuardrailDecision

_P = ParamSpec("_P")
_R = TypeVar("_R")


class Guardrail(Protocol):
    """
    Base protocol for all guardrails: callable with a name.

    Concrete ABC hierarchies narrow the event
    type and add domain-specific attributes.
    """

    name: str

    def __call__(
        self, event: Any
    ) -> GuardrailDecision | Awaitable[GuardrailDecision]: ...


# The third argument is what `Middleware`'s default would supply, spelled out with this
# module's own `_P`/`_R`. Leaving it to the default binds `middleware.core`'s type
# variables instead, and `Generic.__init_subclass__` rejects a base carrying type
# variables absent from `Generic[...]` on Python 3.11+.
class BaseGuardrail(
    ABC, Middleware[_P, _R, _MiddlewareSignature[_P, _R]], Generic[_P, _R]
):
    """Abstract base class for all guardrails."""

    name: str

    def __init__(self, name: str | None = None):
        """Initialize the guardrail.

        Args:
            name: Rail name for traces and debugging; defaults to the class name.
        """
        super().__init__(fn=self._middleware_fn, name=name or self.__class__.__name__)

    @abstractmethod
    async def _middleware_fn(
        self,
        call: Callable[_P, Awaitable[_R]],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> _R:
        pass
