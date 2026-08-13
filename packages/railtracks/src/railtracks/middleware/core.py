from __future__ import annotations

import inspect
import uuid
from typing import (
    Awaitable,
    Callable,
    Concatenate,
    Generic,
    ParamSpec,
    TypeAlias,
    TypeVar,
    overload,
)

from railtracks.events.middleware import MiddlewareCreationEvent
from railtracks.events.send import emit
from railtracks.utils.logging.create import get_rt_logger

_P = ParamSpec("_P")
_R = TypeVar("_R")


def _require_callable(fn: Callable, role: str) -> None:
    if not callable(fn):
        raise TypeError(f"{role} must be callable, got {fn!r}")


def _require_async(fn: Callable, role: str) -> None:
    _require_callable(fn, role)
    if not inspect.iscoroutinefunction(fn):
        raise TypeError(
            f"{role} must be an async function (coroutine function): {fn!r}"
        )


logger = get_rt_logger(__name__)


class Middleware(Generic[_P, _R]):
    """Execution-control middleware: wraps a callable to control how it is invoked.

    Built from an async call-style function ``fn(call, *args, **kwargs)`` where
    ``call`` is the next callable in the chain::

        @wrap_node
        async def retry(call, *args, **kwargs):
            for _ in range(3):
                try:
                    return await call(*args, **kwargs)
                except Exception:
                    pass
            raise RuntimeError("All retries exhausted")

    ``fn`` must be ``async``; passing a plain ``def`` raises ``TypeError``.
    """

    def __init__(
        self,
        fn: Callable[Concatenate[Callable[_P, Awaitable[_R]], _P], Awaitable[_R]],
        name: str | None = None,
    ) -> None:
        _require_async(fn, "Middleware function")
        self._fn = fn
        self.name = name if name is not None else fn.__name__
        self.type_id = str(
            uuid.uuid4()
        )  # identifies this middleware definition, shared by every invocation

        self._has_registered = False

    async def start_creation_task(self):
        if self._has_registered:
            return

        self._has_registered = True
        event = MiddlewareCreationEvent(
            middleware_type_id=self.type_id,
            middleware_name=self.name,
        )
        return await emit(event)

    def wrap(self, inner: Callable[_P, Awaitable[_R]]) -> Callable[_P, Awaitable[_R]]:
        """Compose this middleware onto ``inner``, returning a new callable with the same signature."""
        fn = self._fn

        async def wrapped(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            return await fn(inner, *args, **kwargs)

        return wrapped

    def __repr__(self) -> str:
        return f"Middleware({self._fn.__name__})"

    def middleware_type(self) -> str:
        return "General"


_Wrapper: TypeAlias = Callable[
    Concatenate[Callable[_P, Awaitable[_R]], _P], Awaitable[_R]
]


@overload
def wrap_node(
    fn: _Wrapper[_P, _R], /, *, name: str | None = None
) -> Middleware[_P, _R]: ...
@overload
def wrap_node(
    *, name: str | None = None
) -> Callable[[_Wrapper[_P, _R]], Middleware[_P, _R]]: ...


def wrap_node(
    fn: _Wrapper[_P, _R] | None = None,
    /,
    *,
    name: str | None = None,
) -> Middleware[_P, _R] | Callable[[_Wrapper[_P, _R]], Middleware[_P, _R]]:
    if fn is None:
        return lambda f: Middleware(f, name=name)
    return Middleware(fn, name=name)
