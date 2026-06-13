"""Unified middleware primitives shared by every entry point in the system.

Two primitives wrap *any* callable (a function node, an agent, a tool, or the
raw LLM model call):

- :class:`Wrapper` — execution control. Receives the inner callable and the call
  arguments and decides whether / how / how many times to invoke it (retries,
  fallbacks, short-circuiting, timing, ...).
- :class:`Gateway` — a one-directional data transform at a boundary. An ``entry``
  gateway transforms the input *before* the callable runs; an ``exit`` gateway
  transforms the output *after*. A gateway may also be check-only — validate and
  raise (a guardrail) or return its input unchanged.

Both can be authored with decorators, but the decorator is **optional** when the
function goes into an explicit :class:`~railtracks.middleware.MiddlewareSet` slot
(``outer_wrappers`` / ``inner_wrappers`` for wrappers, ``gateway_entry`` /
``gateway_exit`` for gateways): the slot implies the role, so a raw async
function is auto-wrapped. The decorator then serves mainly as a checker / marker,
and is only *required* for a bare list, where the role is otherwise ambiguous::

    @wrapper
    async def retry(call, *args, **kwargs):
        for _ in range(3):
            try:
                return await call(*args, **kwargs)
            except Exception:
                continue
        raise


    # entry gateway: placed in `gateway_entry`, transforms input
    @gateway
    async def scrub(*args, **kwargs):
        return scrub_args(args), kwargs  # MUST return (args, kwargs)


    # exit gateway: placed in `gateway_exit`, transforms output
    @gateway
    async def redact(result):
        return redact_response(result)

A ``Gateway`` carries **no** direction — *where you place it* (the
``gateway_entry`` list vs the ``gateway_exit`` list of a
:class:`~railtracks.middleware.MiddlewareSet`) decides when it runs. Write the
function with the signature that matches the slot:

- in ``gateway_entry``: ``(*args, **kwargs) -> ...`` where the return is interpreted as:
    * ``None``                      — check-only; the call passes through unchanged
    * a ``dict``                    — the new keyword args (no positional args)
    * a ``tuple``                   — the new positional args (no keyword args)
    * a ``(tuple, dict)`` 2-tuple   — the new ``(args, kwargs)`` in full
    * ``gateway.args(*a, **k)``     — the same, stated explicitly
  Any other (bare) value raises ``TypeError`` — wrap it (``(x,)`` for a positional
  arg, ``gateway.args(x)`` to be explicit) so the arity is never ambiguous.
- in ``gateway_exit``:  ``(result) -> result`` (``None`` keeps the original result)
"""

from __future__ import annotations

import functools
import inspect
from typing import (
    Any,
    Awaitable,
    Callable,
    Coroutine,
    ParamSpec,
    TypeVar,
)

_P = ParamSpec("_P")
_R = TypeVar("_R")

# A wrapper-author function: (inner_call, *args, **kwargs) -> result. Must be async —
# a wrapper has to ``await`` the inner call, which a sync function cannot do.
WrapperFn = Callable[..., Coroutine[Any, Any, Any]]
# A gateway-author function: entry -> (*args, **kwargs) -> (args, kwargs);
#                            exit  -> (result) -> result. May be async or plain sync.
GatewayFn = Callable[..., Any]


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
    """Tagged container returned by :func:`gateway.args` to state an entry gateway's
    new ``(args, kwargs)`` unambiguously — including multiple positional args and/or
    keyword args, which a bare return value cannot express."""

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


class Wrapper:
    """Execution-control middleware.

    Built from a call-style async function ``fn(call, *args, **kwargs)`` where
    ``call`` is the inner (already-wrapped) callable. The function is responsible
    for invoking ``call`` — it may skip it, retry it, or wrap it in error
    handling.

    ``fn`` must be ``async``: a wrapper has to ``await`` the inner ``call``, which a
    plain ``def`` cannot do without running off the event loop (and the resulting
    loss of the run's context is not acceptable).
    """

    def __init__(self, fn: WrapperFn) -> None:
        _require_async(fn, "Wrapper function")
        self._fn = fn
        functools.update_wrapper(self, fn, updated=())

    def wrap(self, inner: Callable[_P, Awaitable[_R]]) -> Callable[_P, Awaitable[_R]]:
        """Compose this wrapper onto ``inner``, returning a new callable.

        The returned callable carries ``inner``'s parameter and return types, so
        wrapping does not erase the signature of the function being wrapped.
        """

        @functools.wraps(self._fn)
        async def wrapped(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            return await self._fn(inner, *args, **kwargs)

        return wrapped

    @property
    def fn(self) -> WrapperFn:
        return self._fn

    def __repr__(self) -> str:
        return f"Wrapper({getattr(self._fn, '__name__', self._fn)!r})"


class Gateway:
    """Direction-less data-transform middleware.

    Build one with :func:`gateway`; its direction is decided by the slot it is
    placed in (``gateway_entry`` vs ``gateway_exit``)::

        @gateway
        async def scrub(*args, **kwargs):  # used as an entry gateway
            return (clean(args), kwargs)


        @gateway
        async def redact(result):  # used as an exit gateway
            return clean(result)
    """

    def __init__(self, fn: GatewayFn) -> None:
        _require_callable(fn, "Gateway function")
        self._fn = fn
        self._is_async = inspect.iscoroutinefunction(fn)
        functools.update_wrapper(self, fn, updated=())

    async def _invoke(self, *args: Any, **kwargs: Any) -> Any:
        """Call the underlying function, awaiting it if it is async.

        A sync gateway is a quick data transform, so it is run inline (not in a
        thread) — that keeps any ``rt.context`` writes on the current context.
        """
        if self._is_async:
            return await self._fn(*args, **kwargs)
        return self._fn(*args, **kwargs)

    async def apply_entry(self, *args: Any, **kwargs: Any) -> tuple[tuple, dict]:
        """Run as an entry gateway. Returns the new ``(args, kwargs)``.

        The return value is interpreted as:

        - ``None``                       — check-only; pass the call through unchanged.
        - a ``dict``                     — new keyword args, i.e. ``((), the_dict)``.
        - a ``tuple``                    — new positional args, i.e. ``(the_tuple, {})``.
        - a ``(tuple, dict)`` 2-tuple    — the new ``(args, kwargs)`` in full.
        - :func:`gateway.args(*a, **k)`  — the same, stated explicitly.

        Anything else (a bare value) raises ``TypeError``: there is deliberately no
        single-value shorthand, so a returned ``dict`` is never silently unpacked as a
        positional arg. Wrap a lone positional value as ``(x,)`` or ``gateway.args(x)``.
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

    async def apply_exit(self, result: Any) -> Any:
        """Run as an exit gateway. Returns the (possibly transformed) result.

        A check-only gateway may ``return`` nothing (``None``); the original result is
        then passed through unchanged.
        """
        transformed = await self._invoke(result)
        return result if transformed is None else transformed

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Invoke the underlying function directly (a raw pass-through).

        Handy for reusing a generic gateway — e.g. a logger or validator — as an
        ordinary function. This calls the wrapped function as-is and does **not** apply
        the slot semantics; use :meth:`apply_entry` / :meth:`apply_exit` for the
        ``(args, kwargs)`` / result interpretation the engine uses. If the underlying
        function is ``async`` this returns a coroutine to ``await``.
        """
        return self._fn(*args, **kwargs)

    @property
    def fn(self) -> Callable:
        return self._fn

    def __repr__(self) -> str:
        return f"Gateway({getattr(self._fn, '__name__', self._fn)!r})"


def wrapper(fn: WrapperFn) -> Wrapper:
    """Decorator: turn a call-style async function into a :class:`Wrapper`."""
    return Wrapper(fn)


def _gateway_args(*args: Any, **kwargs: Any) -> _GatewayArgs:
    """Build the explicit ``(args, kwargs)`` an entry gateway should produce.

    Use it to state both positional and keyword args at once (a returned ``tuple`` is
    positional-only and a returned ``dict`` is keyword-only)::

        @rt.gateway
        async def reorder(a, b):
            return rt.gateway.args(b, a, flag=True)  # -> ((b, a), {"flag": True})
    """
    return _GatewayArgs(args, kwargs)


def gateway(fn: GatewayFn) -> Gateway:
    """Decorator: turn a function into a (direction-less) :class:`Gateway`.

    ``fn`` may be ``async`` or plain ``def`` (a sync gateway is run inline).

    See :meth:`Gateway.apply_entry` for how an entry gateway's return is interpreted;
    use :func:`gateway.args` to specify multiple positional/keyword args explicitly."""
    return Gateway(fn)


# Expose the explicit-args helper as `gateway.args(...)`.
gateway.args = _gateway_args
