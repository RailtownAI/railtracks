"""Tests for async (``async def``) guardrails.

A guard's ``__call__`` may be sync or async; the rail evaluator awaits it before
dispatching the decision. This is what lets a guard ``await rt.call(...)`` and
delegate the judgement to another agent (issue #1466).
"""

from __future__ import annotations

import pytest
from railtracks.guardrails.core.decision import GuardrailAction, GuardrailDecision
from railtracks.guardrails.core.event import LLMGuardrailEvent, LLMGuardrailPhase
from railtracks.guardrails.llm.concrete import InputGuard, OutputGuard
from railtracks.guardrails.llm.decorators import input_guard, output_guard
from railtracks.llm import MessageHistory
from railtracks.llm.message import AssistantMessage, UserMessage


def _input_event(messages: MessageHistory) -> LLMGuardrailEvent:
    return LLMGuardrailEvent(phase=LLMGuardrailPhase.INPUT, messages=messages)


def _output_event(text: str) -> LLMGuardrailEvent:
    return LLMGuardrailEvent(
        phase=LLMGuardrailPhase.OUTPUT,
        messages=MessageHistory(),
        output_message=AssistantMessage(text),
    )


@pytest.fixture
def history() -> MessageHistory:
    return MessageHistory([UserMessage("hello")])


class TestDecoratorBuildsAsyncGuard:
    def test_async_fn_still_returns_a_guard_instance(self) -> None:
        @input_guard
        async def rail(event) -> GuardrailDecision:
            return GuardrailDecision.allow()

        assert isinstance(rail, InputGuard)
        assert rail.name == "rail"

    def test_async_output_fn_returns_output_guard(self) -> None:
        @output_guard(name="async_out")
        async def rail(event) -> GuardrailDecision:
            return GuardrailDecision.allow()

        assert isinstance(rail, OutputGuard)
        assert rail.name == "async_out"

    def test_async_guard_reports_itself_as_async(self) -> None:
        @input_guard
        async def arail(event) -> GuardrailDecision:
            return GuardrailDecision.allow()

        @input_guard
        def srail(event) -> GuardrailDecision:
            return GuardrailDecision.allow()

        assert arail._is_async() is True
        assert srail._is_async() is False


class TestAsyncRailDispatch:
    """Each decision action dispatches identically for sync and async rails."""

    async def test_allow(self, history) -> None:
        @input_guard
        async def rail(event) -> GuardrailDecision:
            return GuardrailDecision.allow(reason="ok")

        value, traces, decision = await rail.run(
            event=_input_event(history), value=history
        )

        assert decision.action == GuardrailAction.ALLOW
        assert value == history
        assert len(traces) == 1
        assert traces[0].action == "allow"

    async def test_block(self, history) -> None:
        @input_guard
        async def rail(event) -> GuardrailDecision:
            return GuardrailDecision.block(reason="nope", user_facing_message="u")

        _value, traces, decision = await rail.run(
            event=_input_event(history), value=history
        )

        assert decision.action == GuardrailAction.BLOCK
        assert decision.reason == "nope"
        assert traces[-1].action == "block"

    async def test_transform(self, history) -> None:
        replacement = MessageHistory([UserMessage("redacted")])

        @input_guard
        async def rail(event) -> GuardrailDecision:
            return GuardrailDecision.transform_messages(
                messages=replacement, reason="redacted 1"
            )

        value, traces, decision = await rail.run(
            event=_input_event(history), value=history
        )

        assert value == replacement
        assert decision.reason == "redacted 1"
        assert traces[-1].action == "transform"

    async def test_output_phase_async_rail(self) -> None:
        @output_guard
        async def rail(event) -> GuardrailDecision:
            assert event.output_message is not None
            return GuardrailDecision.block(reason="bad output")

        event = _output_event("leaky")
        _value, traces, decision = await rail.run(
            event=event, value=event.output_message
        )

        assert decision.action == GuardrailAction.BLOCK
        assert traces[-1].action == "block"


class TestAsyncRailFailureModes:
    async def test_raising_async_rail_fails_closed(self, history) -> None:
        @input_guard
        async def rail(event) -> GuardrailDecision:
            raise RuntimeError("boom")

        _value, traces, decision = await rail.run(
            event=_input_event(history), value=history
        )

        assert decision.action == GuardrailAction.BLOCK
        assert traces[-1].action == "error"
        assert decision.meta is not None
        assert decision.meta["exception_type"] == "RuntimeError"

    async def test_raising_async_rail_fails_open(self, history) -> None:
        @input_guard(fail_open=True)
        async def rail(event) -> GuardrailDecision:
            raise RuntimeError("boom")

        value, traces, decision = await rail.run(
            event=_input_event(history), value=history
        )

        assert decision == GuardrailDecision.allow()
        assert value == history
        assert traces[-1].action == "error"

    async def test_async_rail_returning_non_decision_is_caught(self, history) -> None:
        """The awaited value is type-checked, so a bad return still fails closed."""

        @input_guard
        async def rail(event):
            return "not a decision"

        _value, traces, decision = await rail.run(
            event=_input_event(history), value=history
        )

        assert decision.action == GuardrailAction.BLOCK
        assert decision.meta is not None
        assert decision.meta["exception_type"] == "TypeError"
        assert "expected GuardrailDecision" in decision.meta["exception_message"]


class TestSyncRailsUnaffected:
    """Regression: the sync path must behave exactly as before."""

    async def test_sync_rail_allows(self, history) -> None:
        @input_guard
        def rail(event) -> GuardrailDecision:
            return GuardrailDecision.allow(reason="ok")

        value, traces, decision = await rail.run(
            event=_input_event(history), value=history
        )

        assert decision.action == GuardrailAction.ALLOW
        assert value == history
        assert traces[0].action == "allow"

    async def test_sync_rail_blocks(self, history) -> None:
        @input_guard
        def rail(event) -> GuardrailDecision:
            return GuardrailDecision.block(reason="nope")

        _value, _traces, decision = await rail.run(
            event=_input_event(history), value=history
        )

        assert decision.action == GuardrailAction.BLOCK


class TestDecideAndAdecide:
    def test_decide_on_async_guard_raises_pointing_at_adecide(self) -> None:
        @input_guard
        async def rail(event) -> GuardrailDecision:
            return GuardrailDecision.allow()

        with pytest.raises(TypeError, match="adecide"):
            rail.decide("hello")

    async def test_adecide_runs_an_async_guard(self) -> None:
        @input_guard
        async def rail(event) -> GuardrailDecision:
            assert isinstance(event, LLMGuardrailEvent)
            return GuardrailDecision.block(reason="flagged")

        decision = await rail.adecide("hello")

        assert decision.action == GuardrailAction.BLOCK
        assert decision.reason == "flagged"

    async def test_adecide_also_accepts_a_sync_guard(self) -> None:
        @input_guard
        def rail(event) -> GuardrailDecision:
            return GuardrailDecision.allow(reason="fine")

        decision = await rail.adecide("hello")

        assert decision.action == GuardrailAction.ALLOW
        assert decision.reason == "fine"

    async def test_adecide_on_output_guard_uses_output_message(self) -> None:
        @output_guard
        async def rail(event) -> GuardrailDecision:
            assert event.output_message.content == "the reply"
            return GuardrailDecision.allow()

        decision = await rail.adecide("the reply")

        assert decision.action == GuardrailAction.ALLOW


class TestDocstringPreserved:
    def test_async_rail_docstring_carried_to_guard_class(self) -> None:
        @input_guard
        async def rail(event) -> GuardrailDecision:
            """My async rail docstring."""
            return GuardrailDecision.allow()

        assert type(rail).__doc__ == "My async rail docstring."
