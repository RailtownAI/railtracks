"""Unified middleware primitives for every Railtracks entry point.

- :class:`Wrapper` — execution control: receives the inner callable and decides
  whether/how/how-many-times to invoke it (retry, fallback, short-circuit, timing).
- :class:`Gateway` — direction-neutral data transform: slot placement decides
  when it runs. ``gateway_entry`` transforms input; ``gateway_exit`` transforms
  output. Check-only gateways validate and raise, or return ``None`` to pass through.

``@wrapper`` / ``@gateway`` are optional in named
:class:`~railtracks.middleware.MiddlewareSet` slots (the slot implies the role
and auto-coerces raw functions); required in bare lists where the role is ambiguous.

Entry gateway return conventions:
``None`` → pass-through · ``tuple`` → new args · ``dict`` → new kwargs ·
``(tuple, dict)`` → full replacement · :func:`gateway.args` → explicit form.
Any other bare value raises ``TypeError``.
"""

from __future__ import annotations

import inspect
from typing import (
    Any,
    Awaitable,
    Callable,
    Concatenate,
    Generic,
    ParamSpec,
    TypeVar,
    overload,
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


class _GatewayArgs:
    """Unambiguous ``(args, kwargs)`` container returned by :func:`gateway.args`."""

    __slots__ = ("args", "kwargs")

    def __init__(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        self.args = args
        self.kwargs = kwargs

    def __repr__(self) -> str:
        inner = ", ".join(
            [repr(a) for a in self.args]
            + [f"{k}={v!r}" for k, v in self.kwargs.items()]
        )
        return f"gateway.args({inner})"


class Wrapper(Generic[_P, _R]):
    """Execution-control middleware: wraps a callable to control how it is invoked.

    Built from an async call-style function ``fn(call, *args, **kwargs)`` where
    ``call`` is the next callable in the chain::

        @wrapper
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
        _require_async(fn, "Wrapper function")
        self._fn = fn

    def wrap(self, inner: Callable[_P, Awaitable[_R]]) -> Callable[_P, Awaitable[_R]]:
        """Compose this wrapper onto ``inner``, returning a new callable with the same signature."""
        fn = self._fn

        async def wrapped(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            return await fn(inner, *args, **kwargs)

        return wrapped

    def __repr__(self) -> str:
        return f"Wrapper({getattr(self._fn, '__name__', self._fn)!r})"


class Gateway(Generic[_P, _R]):
    """Direction-neutral data-transform middleware.

    Slot placement decides direction: ``gateway_entry`` transforms input,
    ``gateway_exit`` transforms output. The same object can serve either::

        @gateway
        async def scrub(*args, **kwargs):  # entry: clean the inputs
            return (clean(args), kwargs)


        @gateway
        async def redact(result):  # exit: clean the output
            return clean(result)
    """

    def __init__(self, fn: Callable[_P, Awaitable[_R] | _R]) -> None:
        _require_callable(fn, "Gateway function")
        self._fn = fn

    async def _invoke(self, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        """Call the underlying function, awaiting it if async.

        Sync gateways run inline (not in a thread) to preserve ``rt.context``
        writes on the current context.
        """
        if inspect.iscoroutinefunction(self._fn):
            result: _R = await self._fn(*args, **kwargs)
        else:
            result: _R = self._fn(*args, **kwargs)

        return result

    async def apply_entry(
        self, *args: _P.args, **kwargs: _P.kwargs
    ) -> tuple[tuple, dict]:
        """Run as an entry gateway; returns the new ``(args, kwargs)``.

        Return-value conventions:

        - ``None``                      — check-only; pass through unchanged.
        - ``tuple``                     — new positional args: ``(the_tuple, {})``.
        - ``dict``                      — new keyword args: ``((), the_dict)``.
        - ``(tuple, dict)`` 2-tuple     — full ``(args, kwargs)`` replacement.
        - :func:`gateway.args(*a, **k)` — same, stated explicitly.

        Any other bare value raises ``TypeError``. Wrap a lone positional as
        ``(x,)`` or ``gateway.args(x)``.
        """
        result = await self._invoke(*args, **kwargs)
        if result is None:
            return args, kwargs
        if isinstance(result, _GatewayArgs):
            return result.args, result.kwargs
        # (args_tuple, kwargs_dict) -> full form. Check before the plain-tuple case.
        if (
            isinstance(result, tuple)
            and len(result) == 2
            and isinstance(result[0], tuple)
            and isinstance(result[1], dict)
        ):
            return result
        if isinstance(result, tuple):
            return result, {}  # positional args only
        if isinstance(result, dict):
            return (), result  # keyword args only
        raise TypeError(
            f"Entry gateway {self._fn!r} must return None, a tuple (positional args), "
            f"a dict (keyword args), a (tuple, dict) pair, or gateway.args(...); "
            f"got {result!r}. Wrap a single positional value as (x,) or gateway.args(x)."
        )

    async def apply_exit(self, result: _R) -> _R:
        """Run as an exit gateway; returns the transformed result. ``None`` keeps the original."""
        transformed = await self._invoke(result)
        return result if transformed is None else transformed

    def __call__(self, *args: _P.args, **kwargs: _P.kwargs):
        """Call the underlying function directly, bypassing slot semantics.

        Use :meth:`apply_entry` / :meth:`apply_exit` for the engine's interpretation.
        Returns a coroutine if the function is ``async``.
        """
        return self._fn(*args, **kwargs)

    @property
    def fn(self) -> Callable[_P, Awaitable[_R] | _R]:
        return self._fn

    def __repr__(self) -> str:
        return f"Gateway({getattr(self._fn, '__name__', self._fn)!r})"


@overload
def wrapper(
    fn: Callable[Concatenate[Callable[_P, Awaitable[_R]], _P], Awaitable[_R]],
) -> Wrapper[_P, _R]: ...


@overload
def wrapper(
    fn: Callable[..., Awaitable[Any]],
) -> Wrapper[Any, Any]: ...


def wrapper(fn: Callable) -> Wrapper:
    """Decorator: turn a call-style async function into a :class:`Wrapper`.

    Explicitly-typed functions (named ``call``, ``x``, ``y``, …) resolve to
    ``Wrapper[_P, _R]``. ``*args, **kwargs`` functions resolve to
    ``Wrapper[Any, Any]`` via the fallback overload — assignable to any typed slot.
    """
    return Wrapper(fn)


def _gateway_args(*args: Any, **kwargs: Any) -> _GatewayArgs:
    """Return an explicit ``(args, kwargs)`` pair for an entry gateway.

    Use when you need both positional and keyword args — a bare ``tuple`` is
    positional-only and a bare ``dict`` is keyword-only::

        @rt.gateway
        async def reorder(a, b):
            return rt.gateway.args(b, a, flag=True)  # -> ((b, a), {"flag": True})
    """
    return _GatewayArgs(args, kwargs)


@overload
def gateway(fn: Callable[_P, Awaitable[_R]]) -> Gateway[_P, _R]: ...


@overload
def gateway(fn: Callable[_P, _R]) -> Gateway[_P, _R]: ...


@overload
def gateway(fn: Callable[..., Any]) -> Gateway[Any, Any]: ...


def gateway(fn: Callable) -> Gateway:
    """Decorator: turn a function into a direction-neutral :class:`Gateway`.

    ``fn`` may be ``async`` or plain ``def`` (sync gateways run inline).
    Explicitly-typed functions resolve to ``Gateway[_P, _R]``; ``*args, **kwargs``
    functions resolve to ``Gateway[Any, Any]`` — assignable to any typed slot.

    See :meth:`Gateway.apply_entry` for return-value conventions; use
    :func:`gateway.args` to specify both positional and keyword args explicitly.
    """
    return Gateway(fn)


# Expose the explicit-args helper as `gateway.args(...)`.
gateway.args = _gateway_args
