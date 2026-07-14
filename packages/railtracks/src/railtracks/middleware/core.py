from __future__ import annotations

import inspect
from typing import (
    Awaitable,
    Callable,
    Concatenate,
    Generic,
    ParamSpec,
    TypeVar,
)

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
    ) -> None:
        _require_async(fn, "Middleware function")
        self._fn = fn

    def wrap(self, inner: Callable[_P, Awaitable[_R]]) -> Callable[_P, Awaitable[_R]]:
        """Compose this middleware onto ``inner``, returning a new callable with the same signature."""
        fn = self._fn

        async def wrapped(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            return await fn(inner, *args, **kwargs)

        return wrapped

    def __repr__(self) -> str:
        return f"Middleware({self._fn.__name__})"


def wrap_node(
    fn: Callable[Concatenate[Callable[_P, Awaitable[_R]], _P], Awaitable[_R]],
) -> Middleware[_P, _R]:
    """
    Decorator to wrap any async wrapper function into a Middleware object. The wrapped function will accept
    """
    return Middleware(fn)
