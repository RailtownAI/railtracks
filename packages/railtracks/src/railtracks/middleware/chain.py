from __future__ import annotations

from typing import (
    Awaitable,
    Callable,
    Generic,
    Iterable,
    ParamSpec,
    TypeVar,
)

from railtracks.events.middleware import (
    MiddlewareFailureEvent,
    MiddlewareInvocationEvent,
    MiddlewareResponseEvent,
)
<<<<<<< HEAD
from railtracks.events.send import pipe
=======
from railtracks.events.send import emit
>>>>>>> feature-branch-observability-update
from railtracks.middleware.core import Middleware
from railtracks.scope_manager import ScopeManager, null_scope_manager

_P = ParamSpec("_P")
_R = TypeVar("_R")


def _scoped(
    m: Middleware[_P, _R],
    inner: Callable[_P, Awaitable[_R]],
    get_scope_manager: Callable[[], ScopeManager],
):
    wrapped = m.wrap(inner)
    middleware_type_id = m.type_id

    async def scoped(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        # we need to ensure that the middleware creation event is sent
        await m.start_creation_task()

        with get_scope_manager().enter_middleware(
            middleware_type_id,
        ):
            invocation_event = MiddlewareInvocationEvent(args=args, kwargs=kwargs)

<<<<<<< HEAD
            await pipe(invocation_event)
=======
            await emit(invocation_event)
>>>>>>> feature-branch-observability-update
            try:
                result = await wrapped(*args, **kwargs)

            except Exception as e:
                event = MiddlewareFailureEvent.from_exception(e)
<<<<<<< HEAD
                await pipe(event)
=======
                await emit(event)
>>>>>>> feature-branch-observability-update
                raise e

            event = MiddlewareResponseEvent(
                response=result,
            )
<<<<<<< HEAD
            await pipe(event)
=======
            await emit(event)
>>>>>>> feature-branch-observability-update

            return result

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
