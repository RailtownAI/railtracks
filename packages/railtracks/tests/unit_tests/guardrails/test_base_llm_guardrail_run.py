"""Unit tests for BaseLLMGuardrail.run() — the single-rail mechanics (allow/transform/
block/exception/wrong-return-type dispatch, fail_open vs fail_closed) that used to be
exercised only indirectly through the now-deleted GuardRunner.
"""

from __future__ import annotations

from railtracks.guardrails.core import (
    GuardrailAction,
    GuardrailDecision,
    InputGuard,
    LLMGuardrailEvent,
    LLMGuardrailPhase,
    OutputGuard,
)
from railtracks.llm import AssistantMessage, MessageHistory, UserMessage


class FnInputGuard(InputGuard):
    """Wrap a plain callable as an InputGuard for testing."""

    def __init__(self, fn, name: str | None = None, fail_open: bool = False):
        super().__init__(name=name, fail_open=fail_open)
        self._decision_fn = fn

    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision:
        return self._decision_fn(event)


class FnOutputGuard(OutputGuard):
    """Wrap a plain callable as an OutputGuard for testing."""

    def __init__(self, fn, name: str | None = None, fail_open: bool = False):
        super().__init__(name=name, fail_open=fail_open)
        self._decision_fn = fn

    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision:
        return self._decision_fn(event)


def _input_event(messages: MessageHistory) -> LLMGuardrailEvent:
    return LLMGuardrailEvent(phase=LLMGuardrailPhase.INPUT, messages=messages)


def _output_event(messages: MessageHistory, output_message) -> LLMGuardrailEvent:
    return LLMGuardrailEvent(
        phase=LLMGuardrailPhase.OUTPUT, messages=messages, output_message=output_message
    )


# ---------------------------------------------------------------------------
# ALLOW
# ---------------------------------------------------------------------------


def test_run_allow_returns_value_unchanged(sample_history):
    guard = FnInputGuard(lambda _e: GuardrailDecision.allow(reason="ok"))
    value, traces, blocked = guard.run(event=_input_event(sample_history), value=sample_history)

    assert value == sample_history
    assert blocked is None
    assert len(traces) == 1
    assert traces[0].action == "allow"


# ---------------------------------------------------------------------------
# TRANSFORM
# ---------------------------------------------------------------------------


def test_run_transform_updates_value(sample_history):
    new_hist = MessageHistory([UserMessage("two")])
    guard = FnInputGuard(
        lambda _e: GuardrailDecision.transform_messages(messages=new_hist, reason="t1")
    )
    value, traces, blocked = guard.run(event=_input_event(sample_history), value=sample_history)

    assert blocked is None
    assert value == new_hist
    assert traces[-1].action == "transform"


def test_run_transform_missing_messages_fail_closed(sample_history):
    class BadTransform(InputGuard):
        def __call__(self, _e: LLMGuardrailEvent) -> GuardrailDecision:
            return GuardrailDecision(
                action=GuardrailAction.TRANSFORM, reason="no messages", messages=None
            )

    guard = BadTransform(fail_open=False)
    value, traces, blocked = guard.run(event=_input_event(sample_history), value=sample_history)

    assert blocked is not None
    assert blocked.action == GuardrailAction.BLOCK
    assert "transform failed" in blocked.reason.lower()
    assert traces[-1].action == "error"


def test_run_transform_missing_messages_fail_open(sample_history):
    class BadTransform(InputGuard):
        def __call__(self, _e: LLMGuardrailEvent) -> GuardrailDecision:
            return GuardrailDecision(
                action=GuardrailAction.TRANSFORM, reason="no messages", messages=None
            )

    guard = BadTransform(fail_open=True)
    value, traces, blocked = guard.run(event=_input_event(sample_history), value=sample_history)

    assert blocked is None
    assert value == sample_history  # unchanged: the failed transform never applied
    assert traces[-1].action == "error"


# ---------------------------------------------------------------------------
# BLOCK
# ---------------------------------------------------------------------------


def test_run_block_stops_regardless_of_fail_open(sample_history):
    for fail_open in (False, True):
        guard = FnInputGuard(
            lambda _e: GuardrailDecision.block(reason="stop", user_facing_message="u"),
            fail_open=fail_open,
        )
        value, traces, blocked = guard.run(event=_input_event(sample_history), value=sample_history)

        assert blocked is not None, f"fail_open={fail_open} should not override an explicit BLOCK"
        assert blocked.action == GuardrailAction.BLOCK
        assert blocked.reason == "stop"
        assert traces[-1].action == "block"


# ---------------------------------------------------------------------------
# Exceptions raised by the guard's __call__
# ---------------------------------------------------------------------------


def test_run_rail_raises_fail_closed(sample_history):
    def boom(_e: LLMGuardrailEvent) -> GuardrailDecision:
        raise RuntimeError("rail error")

    guard = FnInputGuard(boom, fail_open=False)
    value, traces, blocked = guard.run(event=_input_event(sample_history), value=sample_history)

    assert blocked is not None
    assert "raised exception" in blocked.reason.lower()
    assert traces[0].action == "error"
    assert traces[0].meta is not None
    assert traces[0].meta.get("exception_type") == "RuntimeError"


def test_run_rail_raises_fail_open(sample_history):
    def boom(_e: LLMGuardrailEvent) -> GuardrailDecision:
        raise ValueError("x")

    guard = FnInputGuard(boom, fail_open=True)
    value, traces, blocked = guard.run(event=_input_event(sample_history), value=sample_history)

    assert blocked is None
    assert value == sample_history
    assert traces[0].action == "error"


def test_run_wrong_return_type_fail_closed(sample_history):
    def bad(_e: LLMGuardrailEvent):
        return "not a decision"

    guard = FnInputGuard(bad, fail_open=False)
    value, traces, blocked = guard.run(event=_input_event(sample_history), value=sample_history)

    assert blocked is not None
    assert "raised exception" in blocked.reason.lower()
    assert "TypeError" in (traces[0].meta or {}).get("exception_type", "")


# Note: `_dispatch_non_allow_decision` has a defensive "unknown action" branch that
# blocks (or continues, if fail_open) on a GuardrailAction outside ALLOW/TRANSFORM/BLOCK.
# It is not covered here: `_trace_from_decision` unconditionally does `decision.action.value`
# *before* dispatch ever runs, so a decision with a non-enum `action` (only reachable via
# GuardrailDecision.model_construct(), bypassing pydantic validation) raises an uncaught
# AttributeError first and never reaches that branch. That's dead code paired with a real
# gap (a malformed decision crashes instead of blocking gracefully) — a fix, not a test.


# ---------------------------------------------------------------------------
# Trace naming
# ---------------------------------------------------------------------------


def test_trace_rail_name_fallback_to_class(sample_history):
    class UnnamedRail(InputGuard):
        def __call__(self, _e: LLMGuardrailEvent) -> GuardrailDecision:
            return GuardrailDecision.allow()

    guard = UnnamedRail()
    _value, traces, _blocked = guard.run(event=_input_event(sample_history), value=sample_history)
    assert traces[0].rail_name == "UnnamedRail"


def test_trace_uses_rail_name_attr(sample_history):
    class NamedRail(InputGuard):
        def __call__(self, _e: LLMGuardrailEvent) -> GuardrailDecision:
            return GuardrailDecision.allow()

    guard = NamedRail(name="custom")
    _value, traces, _blocked = guard.run(event=_input_event(sample_history), value=sample_history)
    assert traces[0].rail_name == "custom"


# ---------------------------------------------------------------------------
# OutputGuard shares the same base mechanics — spot-check block/transform.
# ---------------------------------------------------------------------------


def test_run_output_block(sample_history):
    output_message = AssistantMessage("a")
    guard = FnOutputGuard(lambda _e: GuardrailDecision.block(reason="bad output"))
    value, traces, blocked = guard.run(
        event=_output_event(sample_history, output_message), value=output_message
    )

    assert blocked is not None
    assert traces[-1].action == "block"


def test_run_output_transform(sample_history):
    output_message = AssistantMessage("a")
    new_message = AssistantMessage("b")
    guard = FnOutputGuard(
        lambda _e: GuardrailDecision.transform_output(output_message=new_message, reason="fix")
    )
    value, traces, blocked = guard.run(
        event=_output_event(sample_history, output_message), value=output_message
    )

    assert blocked is None
    assert value == new_message
    assert traces[-1].action == "transform"
