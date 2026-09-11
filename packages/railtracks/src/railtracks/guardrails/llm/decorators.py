"""Decorators for authoring guardrails from a plain function.

Mirror the ``@pre_llm`` / ``@post_llm`` middleware decorators: wrap a function
that maps an event to a :class:`GuardrailDecision` and get back a ready-to-use
:class:`InputGuard` / :class:`OutputGuard` instance.

Example::

    @rt.input_guard
    def block_secrets(
        event: rt.guardrails.LLMGuardrailEvent,
    ) -> rt.guardrails.GuardrailDecision:
        for msg in event.messages:
            if isinstance(msg.content, str) and "SECRET" in msg.content:
                return rt.guardrails.GuardrailDecision.block(reason="secret leaked")
        return rt.guardrails.GuardrailDecision.allow()


    @rt.output_guard(fail_open=True)
    def no_profanity(event) -> rt.guardrails.GuardrailDecision: ...

The decorated guard is callable both with an :class:`LLMGuardrailEvent` (how the
guard's middleware invokes it) and with a raw ``str`` / :class:`~railtracks.llm.message.Message`
/ :class:`~railtracks.llm.history.MessageHistory`, which is coerced to the correct
event for the phase via :meth:`convert` before the function sees it.

The wrapped function may be sync or async. An ``async def`` guard is awaited while
its middleware evaluates the rail (``_eval_one_rail``), so it can ``await`` anything
-- including ``rt.call`` into another agent, which is how you build an LLM-judge
rail::

    @rt.input_guard
    async def llm_judge(event):
        verdict = await rt.call(Judge, event.messages[-1].content)
        if "UNSAFE" in str(verdict):
            return rt.guardrails.GuardrailDecision.block(reason="judge flagged input")
        return rt.guardrails.GuardrailDecision.allow()

Note that a rail runs once per *model round-trip*, not once per agent call, so an
async rail on a tool-calling agent fires on every iteration of the tool loop.
"""

from __future__ import annotations

import inspect
from typing import Awaitable, Callable, TypeVar, cast, overload

from railtracks.guardrails.core.decision import GuardrailDecision
from railtracks.guardrails.core.event import LLMGuardrailEvent
from railtracks.guardrails.llm.concrete import InputGuard, OutputGuard
from railtracks.guardrails.llm.llm_guard import BaseLLMGuardrail

_GuardFn = Callable[
    [LLMGuardrailEvent], GuardrailDecision | Awaitable[GuardrailDecision]
]
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

    An ``async def`` ``fn`` produces a guard with an ``async def __call__``, which the
    rail evaluator awaits. Everything downstream of the decision is identical either
    way.
    """
    guard_name = name or fn.__name__

    if inspect.iscoroutinefunction(fn):

        class _FunctionGuard(base):  # type: ignore[valid-type, misc]
            async def __call__(self, event) -> GuardrailDecision:
                if not isinstance(event, LLMGuardrailEvent):
                    event = self.convert(event)
                return await fn(event)

    else:

        class _FunctionGuard(base):  # type: ignore[valid-type, misc, no-redef]
            def __call__(self, event) -> GuardrailDecision:
                if not isinstance(event, LLMGuardrailEvent):
                    event = self.convert(event)
                return cast(GuardrailDecision, fn(event))

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
    ``event.messages``) and returns a :class:`GuardrailDecision`. It may be sync or
    ``async def``; an async rail is awaited, so it can ``await rt.call(...)``.

    Usable bare or parameterized::

        @rt.input_guard
        def guard(event): ...


        @rt.input_guard(name="my_rail", fail_open=True)
        async def guard(event): ...

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
    ``event.output_message``) and returns a :class:`GuardrailDecision`. It may be
    sync or ``async def``; an async rail is awaited, so it can ``await rt.call(...)``.
    Intermediate tool-call turns are skipped by :class:`OutputGuard`, so the
    function fires only on the final reply.

    Usable bare or parameterized::

        @rt.output_guard
        def guard(event): ...


        @rt.output_guard(name="my_rail", fail_open=True)
        async def guard(event): ...

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
