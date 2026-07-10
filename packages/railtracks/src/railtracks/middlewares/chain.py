from __future__ import annotations

from typing import (
    Awaitable,
    Callable,
    Generic,
    Iterable,
    ParamSpec,
    TypeVar,
)

from railtracks.middlewares.core import Middleware

_P = ParamSpec("_P")
_R = TypeVar("_R")


class MiddlewareChain(Generic[_P, _R]):
    def __init__(
        self,
        middleware: Iterable[Middleware[_P, _R]] | None = None,
    ) -> None:
        self._middleware: list[Middleware[_P, _R]] = (
            list(middleware) if middleware is not None else []
        )

    def add_middleware(self, m: Middleware[_P, _R]) -> None:
        """Append a user outer middleware (outermost band). Runs around the whole call."""
        self._middleware.append(m)

    @property
    def middleware(self) -> list[Middleware[_P, _R]]:
        """User-layer outer middleware (excludes system-registered layers)."""
        return list(self._middleware)

    async def run(
        self,
        core: Callable[_P, Awaitable[_R]],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> _R:
        func = core
        for m in reversed(self._middleware):
            func = m.wrap(func)

        return await func(*args, **kwargs)

    def __repr__(self) -> str:
        return f"MiddlewareChain(middleware={self._middleware!r}, "
