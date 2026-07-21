from __future__ import annotations

import railtracks as rt
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


class TestReturnsGuardInstance:
    def test_bare_input_guard_is_input_guard(self) -> None:
        @input_guard
        def rail(event) -> GuardrailDecision:
            return GuardrailDecision.allow()

        assert isinstance(rail, InputGuard)

    def test_bare_output_guard_is_output_guard(self) -> None:
        @output_guard
        def rail(event) -> GuardrailDecision:
            return GuardrailDecision.allow()

        assert isinstance(rail, OutputGuard)

    def test_parameterized_forms_return_guards(self) -> None:
        @input_guard(name="in")
        def in_rail(event) -> GuardrailDecision:
            return GuardrailDecision.allow()

        @output_guard(fail_open=True)
        def out_rail(event) -> GuardrailDecision:
            return GuardrailDecision.allow()

        assert isinstance(in_rail, InputGuard)
        assert isinstance(out_rail, OutputGuard)


class TestExposedOnPublicApi:
    def test_top_level_and_namespace(self) -> None:
        assert rt.input_guard is input_guard
        assert rt.output_guard is output_guard
        assert rt.guardrails.input_guard is input_guard
        assert rt.guardrails.output_guard is output_guard


class TestNaming:
    def test_name_defaults_to_function_name(self) -> None:
        @input_guard
        def my_rail(event) -> GuardrailDecision:
            return GuardrailDecision.allow()

        assert my_rail.name == "my_rail"

    def test_explicit_name_wins(self) -> None:
        @input_guard(name="custom")
        def my_rail(event) -> GuardrailDecision:
            return GuardrailDecision.allow()

        assert my_rail.name == "custom"


class TestDecisions:
    def test_allow(self) -> None:
        @input_guard
        def rail(event) -> GuardrailDecision:
            return GuardrailDecision.allow()

        decision = rail(_input_event(MessageHistory([UserMessage("hi")])))
        assert decision.action == GuardrailAction.ALLOW

    def test_block(self) -> None:
        @input_guard
        def rail(event) -> GuardrailDecision:
            for msg in event.messages:
                if isinstance(msg.content, str) and "SECRET" in msg.content:
                    return GuardrailDecision.block(reason="secret leaked")
            return GuardrailDecision.allow()

        blocked = rail(_input_event(MessageHistory([UserMessage("my SECRET key")])))
        allowed = rail(_input_event(MessageHistory([UserMessage("hello")])))
        assert blocked.action == GuardrailAction.BLOCK
        assert allowed.action == GuardrailAction.ALLOW

    def test_output_transform(self) -> None:
        @output_guard
        def rail(event) -> GuardrailDecision:
            return GuardrailDecision.transform_output(
                AssistantMessage("[redacted]"), reason="scrubbed"
            )

        decision = rail(_output_event("sensitive"))
        assert decision.action == GuardrailAction.TRANSFORM
        assert decision.output_message.content == "[redacted]"


class TestRawInputCoercion:
    """The decorated guard coerces str/Message/MessageHistory to the phase event."""

    def test_input_guard_accepts_str(self) -> None:
        @input_guard
        def rail(event) -> GuardrailDecision:
            assert isinstance(event, LLMGuardrailEvent)
            assert event.phase == LLMGuardrailPhase.INPUT
            text = event.messages[0].content
            return (
                GuardrailDecision.block(reason="nope")
                if "SECRET" in text
                else GuardrailDecision.allow()
            )

        assert rail("my SECRET key").action == GuardrailAction.BLOCK
        assert rail("hello").action == GuardrailAction.ALLOW

    def test_output_guard_accepts_str(self) -> None:
        @output_guard
        def rail(event) -> GuardrailDecision:
            assert isinstance(event, LLMGuardrailEvent)
            assert event.phase == LLMGuardrailPhase.OUTPUT
            return (
                GuardrailDecision.block(reason="nope")
                if "bad" in event.output_message.content
                else GuardrailDecision.allow()
            )

        assert rail("this is bad").action == GuardrailAction.BLOCK
        assert rail("this is fine").action == GuardrailAction.ALLOW

    def test_decide_helper_works(self) -> None:
        @input_guard
        def rail(event) -> GuardrailDecision:
            return GuardrailDecision.allow(reason="ok")

        assert rail.decide("anything").action == GuardrailAction.ALLOW


class TestRunIntegration:
    """Decorated guards run via .run() like hand-written subclasses."""

    def test_run_allows(self) -> None:
        @input_guard
        def rail(event) -> GuardrailDecision:
            return GuardrailDecision.allow()

        event = _input_event(MessageHistory([UserMessage("hi")]))
        value, traces, decision = rail.run(event=event, value=event.messages)
        assert decision is None
        assert len(traces) == 1

    def test_run_stops_on_block(self) -> None:
        @input_guard
        def rail(event) -> GuardrailDecision:
            return GuardrailDecision.block(reason="blocked")

        event = _input_event(MessageHistory([UserMessage("hi")]))
        _, _, decision = rail.run(event=event, value=event.messages)
        assert decision is not None
        assert decision.action == GuardrailAction.BLOCK


class TestFailOpen:
    def test_fail_open_lets_request_continue_on_error(self) -> None:
        @input_guard(fail_open=True)
        def rail(event) -> GuardrailDecision:
            raise RuntimeError("boom")

        event = _input_event(MessageHistory([UserMessage("hi")]))
        value, traces, decision = rail.run(event=event, value=event.messages)
        assert decision is None  # continued despite the exception
        assert traces  # the exception was recorded

    def test_fail_closed_blocks_on_error(self) -> None:
        @input_guard
        def rail(event) -> GuardrailDecision:
            raise RuntimeError("boom")

        event = _input_event(MessageHistory([UserMessage("hi")]))
        _, _, decision = rail.run(event=event, value=event.messages)
        assert decision is not None
        assert decision.action == GuardrailAction.BLOCK


class TestDocstringPreserved:
    def test_docstring_carried_to_guard_class(self) -> None:
        @input_guard
        def rail(event) -> GuardrailDecision:
            """My rail docstring."""
            return GuardrailDecision.allow()

        assert type(rail).__doc__ == "My rail docstring."
