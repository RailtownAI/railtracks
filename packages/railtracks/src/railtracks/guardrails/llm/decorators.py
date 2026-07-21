"""Decorators for authoring guardrails from a plain function.

Mirror the ``@before_llm`` / ``@after_llm`` middleware decorators: wrap a function
that maps an event to a :class:`GuardrailDecision` and get back a ready-to-use
:class:`InputGuard` / :class:`OutputGuard` instance.

Example::

    @rt.input_guard
    def block_secrets(event: rt.guardrails.LLMGuardrailEvent) -> rt.guardrails.GuardrailDecision:
        for msg in event.messages:
            if isinstance(msg.content, str) and "SECRET" in msg.content:
                return rt.guardrails.GuardrailDecision.block(reason="secret leaked")
        return rt.guardrails.GuardrailDecision.allow()

    @rt.output_guard(fail_open=True)
    def no_profanity(event) -> rt.guardrails.GuardrailDecision:
        ...

The decorated guard is callable both with an :class:`LLMGuardrailEvent` (how the
guard's middleware invokes it) and with a raw ``str`` / :class:`~railtracks.llm.message.Message`
/ :class:`~railtracks.llm.history.MessageHistory`, which is coerced to the correct
event for the phase via :meth:`convert` before the function sees it.

The wrapped function must be synchronous: a guard's ``__call__`` is invoked
synchronously while its middleware evaluates the rail (``_eval_one_rail``), so an
``async def`` would return an un-awaited coroutine.
"""

from __future__ import annotations

from typing import Callable, TypeVar, cast, overload

from railtracks.guardrails.core.decision import GuardrailDecision
from railtracks.guardrails.core.event import LLMGuardrailEvent
from railtracks.guardrails.llm.concrete import InputGuard, OutputGuard
from railtracks.guardrails.llm.llm_guard import BaseLLMGuardrail

_GuardFn = Callable[[LLMGuardrailEvent], GuardrailDecision]
_GuardT = TypeVar("_GuardT", bound=BaseLLMGuardrail)


def _make_guard(
    base: type[_GuardT],
    fn: _GuardFn,
    *,
    name: str | None,
    fail_open: bool,
) -> _GuardT:
    """Build an ``InputGuard``/``OutputGuard`` instance that delegates to ``fn``.

    The generated guard coerces any non-event input to an event via the base's
    phase-aware :meth:`convert`, so ``fn`` always receives an
    :class:`LLMGuardrailEvent`.
    """
    guard_name = name or fn.__name__

    class _FunctionGuard(base):  # type: ignore[valid-type, misc]
        def __call__(self, event) -> GuardrailDecision:
            if not isinstance(event, LLMGuardrailEvent):
                event = self.convert(event)
            return fn(event)

    _FunctionGuard.__name__ = f"{base.__name__}[{guard_name}]"
    _FunctionGuard.__qualname__ = _FunctionGuard.__name__
    _FunctionGuard.__doc__ = fn.__doc__

    guard_cls = cast("type[_GuardT]", _FunctionGuard)
    return guard_cls(name=guard_name, fail_open=fail_open)


@overload
def input_guard(fn: _GuardFn, /) -> InputGuard: ...
@overload
def input_guard(
    *, name: str | None = ..., fail_open: bool = ...
) -> Callable[[_GuardFn], InputGuard]: ...
def input_guard(
    fn: _GuardFn | None = None,
    *,
    name: str | None = None,
    fail_open: bool = False,
):
    """Turn a function into an :class:`InputGuard` instance.

    The function receives an :class:`LLMGuardrailEvent` (INPUT phase; inspect
    ``event.messages``) and returns a :class:`GuardrailDecision`.

    Usable bare or parameterized::

        @rt.input_guard
        def guard(event): ...

        @rt.input_guard(name="my_rail", fail_open=True)
        def guard(event): ...

    Args:
        fn: The guard function (supplied automatically in the bare form).
        name: Rail name for traces; defaults to the function name.
        fail_open: Allow the request through if the guard raises unexpectedly.

    Returns:
        An :class:`InputGuard` instance in the bare form, or a decorator in the
        parameterized form.
    """

    def decorate(func: _GuardFn, /) -> InputGuard:
        return _make_guard(InputGuard, func, name=name, fail_open=fail_open)

    if fn is not None:
        return decorate(fn)
    return decorate


@overload
def output_guard(fn: _GuardFn, /) -> OutputGuard: ...
@overload
def output_guard(
    *, name: str | None = ..., fail_open: bool = ...
) -> Callable[[_GuardFn], OutputGuard]: ...
def output_guard(
    fn: _GuardFn | None = None,
    *,
    name: str | None = None,
    fail_open: bool = False,
):
    """Turn a function into an :class:`OutputGuard` instance.

    The function receives an :class:`LLMGuardrailEvent` (OUTPUT phase; inspect
    ``event.output_message``) and returns a :class:`GuardrailDecision`.
    Intermediate tool-call turns are skipped by :class:`OutputGuard`, so the
    function fires only on the final reply.

    Usable bare or parameterized::

        @rt.output_guard
        def guard(event): ...

        @rt.output_guard(name="my_rail", fail_open=True)
        def guard(event): ...

    Args:
        fn: The guard function (supplied automatically in the bare form).
        name: Rail name for traces; defaults to the function name.
        fail_open: Allow the response through if the guard raises unexpectedly.

    Returns:
        An :class:`OutputGuard` instance in the bare form, or a decorator in the
        parameterized form.
    """

    def decorate(func: _GuardFn, /) -> OutputGuard:
        return _make_guard(OutputGuard, func, name=name, fail_open=fail_open)

    if fn is not None:
        return decorate(fn)
    return decorate
