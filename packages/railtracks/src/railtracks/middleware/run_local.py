"""Per-run state for middleware, declared as a class attribute."""

from __future__ import annotations

from typing import Any, Callable, Generic, TypeVar, overload

from typing_extensions import Self

from railtracks.middleware.core import Middleware

_T = TypeVar("_T")


class RunLocal(Generic[_T]):
    """A middleware attribute that holds a separate value for each run.

    A middleware instance is shared by every run, so a plain attribute is shared
    too. Declare per-run state as a ``RunLocal`` and use it like any attribute: each
    run starts from ``default_factory()`` and never sees another run's value, even
    one running at the same time::

        from railtracks.middleware import Middleware, RunLocal


        class CountCalls(Middleware):
            calls = RunLocal(int)

            def __init__(self):
                super().__init__(self._middleware_fn)

            async def _middleware_fn(self, call, *args, **kwargs):
                self.calls += 1
                return await call(*args, **kwargs)

    Within one run, every node the instance is attached to shares the value, so
    ``CountCalls`` on two tools counts both. Outside a run, the attribute holds the
    most recent run's value, so a finished run stays readable, and ``del`` resets it.
    Calls made outside any run keep a value of their own.

    The value lives with the session and ends with it. It is not part of
    ``rt.context`` and is never saved.

    Args:
        default_factory: Called with no arguments on the first read in each run. Pass
            a type (``int``, ``list``) or a function rather than a shared object, so
            a mutable default is fresh in every run.
    """

    def __init__(self, default_factory: Callable[[], _T]) -> None:
        self._default_factory = default_factory
        self._name = ""

    def __set_name__(self, owner: type[Any], name: str) -> None:
        if not issubclass(owner, Middleware):
            raise TypeError(
                f"RunLocal {name!r} must be declared on a Middleware subclass, "
                f"not {owner.__qualname__}."
            )
        self._name = name

    @overload
    def __get__(self, instance: None, owner: type[Any]) -> Self: ...
    @overload
    def __get__(self, instance: Middleware[..., Any, Any], owner: type[Any]) -> _T: ...
    def __get__(
        self, instance: Middleware[..., Any, Any] | None, owner: type[Any]
    ) -> Self | _T:
        if instance is None:
            return self
        state = instance._run_state()
        if self._name not in state:
            state[self._name] = self._default_factory()
        return state[self._name]

    def __set__(self, instance: Middleware[..., Any, Any], value: _T) -> None:
        instance._run_state()[self._name] = value

    def __delete__(self, instance: Middleware[..., Any, Any]) -> None:
        instance._run_state().pop(self._name, None)
