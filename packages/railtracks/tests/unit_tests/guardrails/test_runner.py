"""Unit tests for GuardRunner."""

from __future__ import annotations

import pytest

from railtracks.guardrails.core import (
    Guard,
    GuardrailAction,
    GuardrailDecision,
    GuardRunner,
    InputGuard,
    LLMGuardrailEvent,
    LLMGuardrailPhase,
    OutputGuard,
)
from railtracks.llm import AssistantMessage, MessageHistory, UserMessage


def make_input_event(messages: MessageHistory | None = None) -> LLMGuardrailEvent:
    return LLMGuardrailEvent(
        phase=LLMGuardrailPhase.INPUT,
        messages=messages or MessageHistory([UserMessage("hi")]),
    )


class CountingInputGuard(InputGuard):
    def __init__(self, decision_fn, name: str | None = None):
        super().__init__(name=name)
        self.decision_fn = decision_fn
        self.count = 0

    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision:
        self.count += 1
        return self.decision_fn(event)


class CountingOutputGuard(OutputGuard):
    def __init__(self, decision_fn, name: str | None = None):
        super().__init__(name=name)
        self.decision_fn = decision_fn
        self.count = 0

    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision:
        self.count += 1
        return self.decision_fn(event)


def test_run_llm_input_empty_rails(sample_history):
    event = make_input_event(sample_history)
    out, traces, blocked = GuardRunner(Guard()).run_llm_input(event)
    assert out == sample_history
    assert traces == []
    assert blocked is None


def test_run_llm_input_forces_input_phase_and_clears_output():
    out_msg = AssistantMessage(content="assistant")
    event = LLMGuardrailEvent(
        phase=LLMGuardrailPhase.OUTPUT,
        messages=MessageHistory([UserMessage("u")]),
        output_message=out_msg,
    )

    seen: list[LLMGuardrailEvent] = []

    def capture(ev: LLMGuardrailEvent) -> GuardrailDecision:
        seen.append(ev)
        return GuardrailDecision.allow()

    g = Guard(input=[capture])
    GuardRunner(g).run_llm_input(event)
    assert len(seen) == 1
    assert seen[0].phase == LLMGuardrailPhase.INPUT
    assert seen[0].output_message is None


def test_run_llm_input_allow_then_allow(sample_history):
    g = Guard(
        input=[
            lambda _e: GuardrailDecision.allow(reason="a"),
            lambda _e: GuardrailDecision.allow(reason="b"),
        ]
    )
    out, traces, blocked = GuardRunner(g).run_llm_input(make_input_event(sample_history))
    assert out == sample_history
    assert blocked is None
    assert [t.action for t in traces] == ["allow", "allow"]


def test_run_llm_input_block_short_circuits(sample_history):
    second = CountingInputGuard(lambda _e: GuardrailDecision.allow())

    g = Guard(
        input=[
            lambda _e: GuardrailDecision.block(reason="stop"),
            second,
        ]
    )
    out, traces, blocked = GuardRunner(g).run_llm_input(make_input_event(sample_history))
    assert out == sample_history
    assert blocked is not None
    assert blocked.action == GuardrailAction.BLOCK
    assert second.count == 0
    assert traces[-1].action == "block"


def test_run_llm_input_transform_updates_value_and_event_for_next_rail(sample_history):
    h2 = MessageHistory([UserMessage("two")])

    def first(_e: LLMGuardrailEvent) -> GuardrailDecision:
        return GuardrailDecision.transform_messages(messages=h2, reason="t1")

    seen: list[str] = []

    def second(e: LLMGuardrailEvent) -> GuardrailDecision:
        seen.append(e.messages[-1].content)  # type: ignore[union-attr]
        return GuardrailDecision.allow()

    g = Guard(input=[first, second])
    out, traces, blocked = GuardRunner(g).run_llm_input(make_input_event(sample_history))
    assert blocked is None
    assert out == h2
    assert seen == ["two"]
    assert [t.action for t in traces] == ["transform", "allow"]


def test_run_llm_input_transform_missing_messages_fail_closed(sample_history):
    class BadTransform:
        name = "BadTransform"
        phase = LLMGuardrailPhase.INPUT

        def __call__(self, _e: LLMGuardrailEvent) -> GuardrailDecision:
            return GuardrailDecision(
                action=GuardrailAction.TRANSFORM,
                reason="no messages",
                messages=None,
            )

    g = Guard(input=[BadTransform()], fail_open=False)
    out, traces, blocked = GuardRunner(g).run_llm_input(make_input_event(sample_history))
    assert blocked is not None
    assert blocked.action == GuardrailAction.BLOCK
    assert "transform failed" in (blocked.reason or "").lower()
    assert traces[-1].action == "error"


def test_run_llm_input_transform_missing_messages_fail_open(sample_history):
    class BadTransform:
        name = "BadTransform"
        phase = LLMGuardrailPhase.INPUT

        def __call__(self, _e: LLMGuardrailEvent) -> GuardrailDecision:
            return GuardrailDecision(
                action=GuardrailAction.TRANSFORM,
                reason="no messages",
                messages=None,
            )

    second = CountingInputGuard(lambda _e: GuardrailDecision.allow())

    g = Guard(input=[BadTransform(), second], fail_open=True)
    out, traces, blocked = GuardRunner(g).run_llm_input(make_input_event(sample_history))
    assert blocked is None
    assert second.count == 1
    assert any(t.action == "error" for t in traces)


def test_run_llm_input_rail_raises_fail_closed(sample_history):
    def boom(_e: LLMGuardrailEvent) -> GuardrailDecision:
        raise RuntimeError("rail error")

    g = Guard(input=[boom], fail_open=False)
    _out, traces, blocked = GuardRunner(g).run_llm_input(make_input_event(sample_history))
    assert blocked is not None
    assert "raised exception" in blocked.reason.lower()
    assert traces[0].action == "error"
    assert traces[0].meta is not None
    assert traces[0].meta.get("exception_type") == "RuntimeError"


def test_run_llm_input_rail_raises_fail_open(sample_history):
    def boom(_e: LLMGuardrailEvent) -> GuardrailDecision:
        raise ValueError("x")

    second = CountingInputGuard(lambda _e: GuardrailDecision.allow())

    g = Guard(input=[boom, second], fail_open=True)
    out, traces, blocked = GuardRunner(g).run_llm_input(make_input_event(sample_history))
    assert blocked is None
    assert second.count == 1
    assert traces[0].action == "error"


def test_run_llm_input_wrong_return_type_fail_closed(sample_history):
    def bad(_e: LLMGuardrailEvent):
        return "not a decision"

    g = Guard(input=[bad], fail_open=False)
    _out, traces, blocked = GuardRunner(g).run_llm_input(make_input_event(sample_history))
    assert blocked is not None
    assert "raised exception" in blocked.reason.lower()
    assert "TypeError" in (traces[0].meta or {}).get("exception_type", "")


def test_run_llm_output_empty_rails():
    hist = MessageHistory([UserMessage("u")])
    assistant = AssistantMessage(content="reply")
    event = LLMGuardrailEvent(
        phase=LLMGuardrailPhase.OUTPUT,
        messages=hist,
        output_message=assistant,
    )
    out, traces, blocked = GuardRunner(Guard()).run_llm_output(event, assistant)
    assert out == assistant
    assert traces == []
    assert blocked is None


def test_run_llm_output_block_short_circuits():
    hist = MessageHistory([UserMessage("u")])
    m0 = AssistantMessage(content="a")
    second = CountingOutputGuard(lambda _e: GuardrailDecision.allow())

    g = Guard(
        output=[
            lambda _e: GuardrailDecision.block(reason="stop"),
            second,
        ]
    )
    _out, _traces, blocked = GuardRunner(g).run_llm_output(
        LLMGuardrailEvent(
            phase=LLMGuardrailPhase.OUTPUT,
            messages=hist,
            output_message=m0,
        ),
        m0,
    )
    assert blocked is not None
    assert second.count == 0


def test_run_llm_output_transform_chain():
    hist = MessageHistory([UserMessage("u")])
    m0 = AssistantMessage(content="a")
    m1 = AssistantMessage(content="b")

    def t1(_e: LLMGuardrailEvent) -> GuardrailDecision:
        return GuardrailDecision.transform_output(output_message=m1, reason="t1")

    seen: list[str] = []

    def t2(e: LLMGuardrailEvent) -> GuardrailDecision:
        assert e.output_message is not None
        seen.append(e.output_message.content)  # type: ignore[arg-type]
        return GuardrailDecision.allow()

    g = Guard(output=[t1, t2])
    out, traces, blocked = GuardRunner(g).run_llm_output(
        LLMGuardrailEvent(
            phase=LLMGuardrailPhase.OUTPUT,
            messages=hist,
            output_message=m0,
        ),
        m0,
    )
    assert blocked is None
    assert out == m1
    assert seen == ["b"]


def test_run_llm_output_transform_missing_output_fail_closed():
    hist = MessageHistory([UserMessage("u")])
    m0 = AssistantMessage(content="a")

    class BadOut:
        name = "BadOut"
        phase = LLMGuardrailPhase.OUTPUT

        def __call__(self, _e: LLMGuardrailEvent) -> GuardrailDecision:
            return GuardrailDecision(
                action=GuardrailAction.TRANSFORM,
                reason="x",
                output_message=None,
            )

    g = Guard(output=[BadOut()], fail_open=False)
    _out, traces, blocked = GuardRunner(g).run_llm_output(
        LLMGuardrailEvent(
            phase=LLMGuardrailPhase.OUTPUT,
            messages=hist,
            output_message=m0,
        ),
        m0,
    )
    assert blocked is not None
    assert traces[-1].action == "error"


def test_trace_rail_name_fallback_to_class():
    class UnnamedRail:
        phase = LLMGuardrailPhase.INPUT

        def __call__(self, _e: LLMGuardrailEvent) -> GuardrailDecision:
            return GuardrailDecision.allow()

    g = Guard(input=[UnnamedRail()])
    _out, traces, _b = GuardRunner(g).run_llm_input(make_input_event())
    assert traces[0].rail_name == "UnnamedRail"


def test_trace_uses_rail_name_attr():
    class NamedRail:
        name = "custom"
        phase = LLMGuardrailPhase.INPUT

        def __call__(self, _e: LLMGuardrailEvent) -> GuardrailDecision:
            return GuardrailDecision.allow()

    g = Guard(input=[NamedRail()])
    _out, traces, _b = GuardRunner(g).run_llm_input(make_input_event())
    assert traces[0].rail_name == "custom"
