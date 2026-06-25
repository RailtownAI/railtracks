"""Unified middleware primitives for every Railtracks entry point.

- :class:`Wrapper` — execution control: receives the inner callable and decides
  whether/how/how-many-times to invoke it (retry, fallback, short-circuit, timing).
  Use ``@wrapper`` for any wrapper function — the mode (streaming or
  non-streaming) is auto-detected from the function shape (``yield`` vs
  ``return await``).
- :class:`Gate` — direction-neutral data transform: slot placement decides
  when it runs. ``entry_gate`` transforms input; ``exit_gate`` transforms
  output. Check-only gates validate and raise, or return ``None`` to pass through.

``@wrapper`` / ``@gate`` are optional in named
:class:`~railtracks.middleware.MiddlewareChain` slots (the slot implies the role
and auto-coerces raw functions); required in bare lists where the role is ambiguous.

Entry gate return conventions:
``None`` → pass-through · ``tuple`` → new args · ``dict`` → new kwargs ·
``(tuple, dict)`` → full replacement · :func:`gate.args` → explicit form.
Any other bare value raises ``TypeError``.
"""

from __future__ import annotations

import inspect
from typing import (
    Any,
    AsyncGenerator,
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
_TChunk = TypeVar("_TChunk")


def _require_callable(fn: Callable, role: str) -> None:
    if not callable(fn):
        raise TypeError(f"{role} must be callable, got {fn!r}")


# ---------------------------------------------------------------------------
# Wrapper
# ---------------------------------------------------------------------------


class Wrapper(Generic[_P, _R]):
    """Execution-control middleware: wraps a callable to control how it is invoked.

    The wrapper mode is auto-detected from the function shape:

    **Non-streaming** — coroutine function (``return await``)::

        @wrapper
        async def retry(call, *args, **kwargs):
            for _ in range(3):
                try:
                    return await call(*args, **kwargs)
                except Exception:
                    pass
            raise RuntimeError("All retries exhausted")

    **Streaming** — async generator function (``yield``)::

        @wrapper
        async def log_chunks(call, *args, **kwargs):
            async for chunk in call(*args, **kwargs):
                print(chunk)
                yield chunk

    ``fn`` must be ``async``; a plain ``def`` raises ``TypeError``.

    On the non-streaming path a streaming wrapper is a transparent pass-through
    (``wrap()`` returns ``inner`` unchanged), so mixing both kinds in one
    :class:`~railtracks.middleware.MiddlewareChain` is safe.
    """

    def __init__(self, fn: Callable) -> None:
        _require_callable(fn, "Wrapper function")
        if inspect.isasyncgenfunction(fn):
            self._stream = True
        elif inspect.iscoroutinefunction(fn):
            self._stream = False
        else:
            raise TypeError(
                f"Wrapper function must be an async coroutine function "
                f"(async def ... return await ...) or an async generator function "
                f"(async def ... yield ...): {fn!r}"
            )
        self._fn = fn

    def wrap(self, inner: Callable[_P, Awaitable[_R]]) -> Callable[_P, Awaitable[_R]]:
        """Compose this wrapper onto ``inner``, returning a new callable with the same signature.

        For streaming wrappers this is a transparent pass-through — the
        streaming logic lives in :meth:`wrap_stream`.
        """
        if self._stream:
            return inner

        fn = self._fn

        async def wrapped(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            return await fn(inner, *args, **kwargs)

        return wrapped

    def wrap_stream(
        self,
        inner: Callable[..., AsyncGenerator[_TChunk, None]],
    ) -> Callable[..., AsyncGenerator[_TChunk, None]]:
        """Compose this wrapper onto a streaming ``inner`` factory.

        For plain (non-stream) wrappers: transparent pass-through — every chunk
        is forwarded unchanged so existing ``@wrapper`` wrappers work in the
        streaming path without modification.

        For streaming wrappers: delegates to the user-supplied async generator
        function, which receives ``(inner_factory, *args, **kwargs)``.
        """
        if not self._stream:
            async def pass_through(*args: Any, **kwargs: Any) -> AsyncGenerator[_TChunk, None]:
                async for chunk in inner(*args, **kwargs):
                    yield chunk

            return pass_through

        fn = self._fn

        async def wrapped(*args: Any, **kwargs: Any) -> AsyncGenerator[_TChunk, None]:
            async for chunk in fn(inner, *args, **kwargs):
                yield chunk

        return wrapped

    def __repr__(self) -> str:
        name = getattr(self._fn, "__name__", self._fn)
        if self._stream:
            return f"Wrapper({name!r}, stream=True)"
        return f"Wrapper({name!r})"


@overload
def wrapper(
    fn: Callable[Concatenate[Callable[_P, Awaitable[_R]], _P], Awaitable[_R]],
) -> Wrapper[_P, _R]: ...


@overload
def wrapper(
    fn: Callable[..., Awaitable[Any]],
) -> Wrapper[Any, Any]: ...


@overload
def wrapper(
    fn: Callable[..., AsyncGenerator[Any, None]],
) -> Wrapper[Any, Any]: ...


def wrapper(fn: Callable) -> Wrapper:
    """Decorator: turn a call-style async function into a :class:`Wrapper`.

    The wrapper mode is auto-detected from ``fn``'s shape:

    - **coroutine function** (``return await``) → non-streaming wrapper,
      active on ``MiddlewareChain.run()``.
    - **async generator function** (``yield``) → streaming wrapper,
      active on ``MiddlewareChain.run_stream()``.

    Non-streaming example::

        @wrapper
        async def retry(call, *args, **kwargs):
            for _ in range(3):
                try:
                    return await call(*args, **kwargs)
                except Exception:
                    pass
            raise RuntimeError("All retries exhausted")

    Streaming example::

        @wrapper
        async def log_chunks(call, *args, **kwargs):
            async for chunk in call(*args, **kwargs):
                print(chunk)
                yield chunk

    A plain ``def`` (neither coroutine nor async generator) raises ``TypeError``
    at decoration time.

    Explicitly-typed direct-decoration resolves to ``Wrapper[_P, _R]``;
    ``*args, **kwargs`` functions resolve to ``Wrapper[Any, Any]``.
    """
    return Wrapper(fn)


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------


class _GateArgs:
    """Unambiguous ``(args, kwargs)`` container returned by :func:`gate.args`."""

    __slots__ = ("args", "kwargs")

    def __init__(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        self.args = args
        self.kwargs = kwargs

    def __repr__(self) -> str:
        inner = ", ".join(
            [repr(a) for a in self.args]
            + [f"{k}={v!r}" for k, v in self.kwargs.items()]
        )
        return f"gate.args({inner})"


class Gate(Generic[_P, _R]):
    """Direction-neutral data-transform middleware.

    Slot placement decides direction: ``entry_gate`` transforms input,
    ``exit_gate`` transforms output. The same object can serve either::

        @gate
        async def scrub(*args, **kwargs):  # entry: clean the inputs
            return (clean(args), kwargs)


        @gate
        async def redact(result):  # exit: clean the output
            return clean(result)
    """

    def __init__(self, fn: Callable[_P, Awaitable[_R] | _R]) -> None:
        _require_callable(fn, "Gate function")
        self._fn = fn

    async def _invoke(self, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        """Call the underlying function, awaiting it if async.

        Sync gates run inline (not in a thread) to preserve ``rt.context``
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
        """Run as an entry gate; returns the new ``(args, kwargs)``.

        Return-value conventions:

        - ``None``                      — check-only; pass through unchanged.
        - ``tuple``                     — new positional args: ``(the_tuple, {})``.
        - ``dict``                      — new keyword args: ``((), the_dict)``.
        - ``(tuple, dict)`` 2-tuple     — full ``(args, kwargs)`` replacement.
        - :func:`gate.args(*a, **k)`    — same, stated explicitly.

        Any other bare value raises ``TypeError``. Wrap a lone positional as
        ``(x,)`` or ``gate.args(x)``.
        """
        result = await self._invoke(*args, **kwargs)
        if result is None:
            return args, kwargs
        if isinstance(result, _GateArgs):
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
            f"Entry gate {self._fn!r} must return None, a tuple (positional args), "
            f"a dict (keyword args), a (tuple, dict) pair, or gate.args(...); "
            f"got {result!r}. Wrap a single positional value as (x,) or gate.args(x)."
        )

    async def apply_exit(self, result: _R) -> _R:
        """Run as an exit gate; returns the transformed result. ``None`` keeps the original."""
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
        return f"Gate({getattr(self._fn, '__name__', self._fn)!r})"


def _gate_args(*args: Any, **kwargs: Any) -> _GateArgs:
    """Return an explicit ``(args, kwargs)`` pair for an entry gate.

    Use when you need both positional and keyword args — a bare ``tuple`` is
    positional-only and a bare ``dict`` is keyword-only::

        @rt.gate
        async def reorder(a, b):
            return rt.gate.args(b, a, flag=True)  # -> ((b, a), {"flag": True})
    """
    return _GateArgs(args, kwargs)


@overload
def gate(fn: Callable[_P, Awaitable[_R]]) -> Gate[_P, _R]: ...


@overload
def gate(fn: Callable[_P, _R]) -> Gate[_P, _R]: ...


@overload
def gate(fn: Callable[..., Any]) -> Gate[Any, Any]: ...


def gate(fn: Callable) -> Gate:
    """Decorator: turn a function into a direction-neutral :class:`Gate`.

    ``fn`` may be ``async`` or plain ``def`` (sync gates run inline).
    Explicitly-typed functions resolve to ``Gate[_P, _R]``; ``*args, **kwargs``
    functions resolve to ``Gate[Any, Any]`` — assignable to any typed slot.

    See :meth:`Gate.apply_entry` for return-value conventions; use
    :func:`gate.args` to specify both positional and keyword args explicitly.
    """
    return Gate(fn)


# Expose the explicit-args helper as `gate.args(...)`.
gate.args = _gate_args
