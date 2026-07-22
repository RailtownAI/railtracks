from __future__ import annotations

from typing import (
    Awaitable,
    Callable,
    Generic,
    Iterable,
    ParamSpec,
    TypeVar,
)

from railtracks.middleware.core import Middleware
from railtracks.scope_manager import ScopeManager, null_scope_manager
from uuid import uuid4
_P = ParamSpec("_P")
_R = TypeVar("_R")


def _scoped(m: Middleware[_P, _R], inner: Callable[_P, Awaitable[_R]], get_scope_manager: Callable[[], ScopeManager]):
    wrapped = m.wrap(inner)
    identifier = str(uuid4())

    async def scoped(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        with get_scope_manager().enter_middleware(identifier,):
            return await wrapped(*args, **kwargs)

    return scoped


class MiddlewareChain(Generic[_P, _R]):
    def __init__(
        self,
        middleware: Iterable[Middleware[_P, _R]] | None = None,
        get_scope_manager: Callable[[], ScopeManager] = null_scope_manager,
    ) -> None:
        self._middleware: list[Middleware[_P, _R]] = (
            list(middleware) if middleware is not None else []
        )
        self.get_scope_manager = get_scope_manager

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
            func = _scoped(m, func, self.get_scope_manager)

        return await func(*args, **kwargs)

    def __repr__(self) -> str:
        return f"MiddlewareChain(middleware={self._middleware!r}, "
