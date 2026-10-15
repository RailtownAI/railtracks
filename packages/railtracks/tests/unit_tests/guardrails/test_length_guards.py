"""Unit tests for InputLengthGuard and OutputLengthGuard."""

from __future__ import annotations

import pytest
from railtracks.guardrails.core.decision import GuardrailAction
from railtracks.guardrails.core.event import LLMGuardrailEvent, LLMGuardrailPhase
from railtracks.llm import MessageHistory, UserMessage
from railtracks.llm.message import AssistantMessage
from railtracks.prebuilt.guardrails import InputLengthGuard, OutputLengthGuard

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _input_event(text: str) -> LLMGuardrailEvent:
    return LLMGuardrailEvent(
        phase=LLMGuardrailPhase.INPUT,
        messages=MessageHistory([UserMessage(text)]),
    )


def _output_event(text: str) -> LLMGuardrailEvent:
    return LLMGuardrailEvent(
        phase=LLMGuardrailPhase.OUTPUT,
        messages=MessageHistory([UserMessage("prompt")]),
        output_message=AssistantMessage(text),
    )


# ---------------------------------------------------------------------------
# InputLengthGuard
# ---------------------------------------------------------------------------


class TestInputLengthGuard:
    def test_default_max_chars(self):
        guard = InputLengthGuard()
        assert guard.max_chars == 4096

    def test_custom_max_chars(self):
        guard = InputLengthGuard(max_chars=100)
        assert guard.max_chars == 100

    def test_invalid_max_chars_raises(self):
        with pytest.raises(ValueError, match="max_chars"):
            InputLengthGuard(max_chars=0)
        with pytest.raises(ValueError, match="max_chars"):
            InputLengthGuard(max_chars=-10)

    def test_allows_short_input(self):
        guard = InputLengthGuard(max_chars=50)
        event = _input_event("hello")
        decision = guard(event)
        assert decision.action == GuardrailAction.ALLOW
        assert decision.meta["total_chars"] == 5

    def test_blocks_long_input(self):
        guard = InputLengthGuard(max_chars=10)
        event = _input_event("this is definitely longer than ten characters")
        decision = guard(event)
        assert decision.action == GuardrailAction.BLOCK
        assert decision.meta["max_chars"] == 10
        assert decision.user_facing_message is not None

    def test_exact_limit_is_allowed(self):
        guard = InputLengthGuard(max_chars=5)
        event = _input_event("hello")  # exactly 5 chars
        decision = guard(event)
        assert decision.action == GuardrailAction.ALLOW

    def test_one_over_limit_is_blocked(self):
        guard = InputLengthGuard(max_chars=5)
        event = _input_event("hello!")  # 6 chars
        decision = guard(event)
        assert decision.action == GuardrailAction.BLOCK

    def test_meta_contains_expected_keys(self):
        guard = InputLengthGuard(max_chars=100)
        event = _input_event("hi")
        decision = guard(event)
        assert "total_chars" in decision.meta
        assert "max_chars" in decision.meta

    def test_custom_name(self):
        guard = InputLengthGuard(max_chars=100, name="my-input-guard")
        assert guard.name == "my-input-guard"

    def test_default_name_is_class_name(self):
        guard = InputLengthGuard()
        assert guard.name == "InputLengthGuard"

    def test_phase_is_input(self):
        from railtracks.guardrails.core.event import LLMGuardrailPhase

        guard = InputLengthGuard()
        assert guard.phase == LLMGuardrailPhase.INPUT


# ---------------------------------------------------------------------------
# OutputLengthGuard
# ---------------------------------------------------------------------------


class TestOutputLengthGuard:
    def test_default_max_chars(self):
        guard = OutputLengthGuard()
        assert guard.max_chars == 2048

    def test_custom_max_chars(self):
        guard = OutputLengthGuard(max_chars=200)
        assert guard.max_chars == 200

    def test_invalid_max_chars_raises(self):
        with pytest.raises(ValueError, match="max_chars"):
            OutputLengthGuard(max_chars=0)

    def test_allows_short_output(self):
        guard = OutputLengthGuard(max_chars=100)
        event = _output_event("short reply")
        decision = guard(event)
        assert decision.action == GuardrailAction.ALLOW

    def test_blocks_long_output(self):
        guard = OutputLengthGuard(max_chars=10)
        event = _output_event("this reply is way too long for the limit")
        decision = guard(event)
        assert decision.action == GuardrailAction.BLOCK
        assert decision.meta["max_chars"] == 10

    def test_allows_when_no_output_message(self):
        guard = OutputLengthGuard(max_chars=10)
        event = LLMGuardrailEvent(
            phase=LLMGuardrailPhase.OUTPUT,
            messages=MessageHistory([UserMessage("prompt")]),
            output_message=None,
        )
        decision = guard(event)
        assert decision.action == GuardrailAction.ALLOW

    def test_exact_limit_is_allowed(self):
        guard = OutputLengthGuard(max_chars=5)
        event = _output_event("hello")
        decision = guard(event)
        assert decision.action == GuardrailAction.ALLOW

    def test_one_over_limit_is_blocked(self):
        guard = OutputLengthGuard(max_chars=5)
        event = _output_event("hello!")
        decision = guard(event)
        assert decision.action == GuardrailAction.BLOCK

    def test_phase_is_output(self):
        from railtracks.guardrails.core.event import LLMGuardrailPhase

        guard = OutputLengthGuard()
        assert guard.phase == LLMGuardrailPhase.OUTPUT

    def test_custom_name(self):
        guard = OutputLengthGuard(max_chars=100, name="my-output-guard")
        assert guard.name == "my-output-guard"


# ---------------------------------------------------------------------------
# Non-string content (regression for tool messages / structured output)
# ---------------------------------------------------------------------------


class TestLengthGuardsNonStringContent:
    """Guards must count characters for ToolResponse, ToolCalls and BaseModel."""

    def test_input_tool_message_allowed(self):
        from railtracks.llm import ToolMessage, ToolResponse

        guard = InputLengthGuard(max_chars=1000)
        history = MessageHistory(
            [
                UserMessage("What is the weather?"),
                ToolMessage(ToolResponse(identifier="1", name="weather", result="15C")),
            ]
        )
        event = LLMGuardrailEvent(phase=LLMGuardrailPhase.INPUT, messages=history)
        decision = guard(event)
        assert decision.action == GuardrailAction.ALLOW
        # "What is the weather?" = 20, "15C" = 3 → 23
        assert decision.meta["total_chars"] == 23

    def test_input_tool_message_blocked(self):
        from railtracks.llm import ToolMessage, ToolResponse

        guard = InputLengthGuard(max_chars=10)
        history = MessageHistory(
            [
                UserMessage("hi"),
                ToolMessage(
                    ToolResponse(identifier="1", name="weather", result="15 degrees C")
                ),
            ]
        )
        event = LLMGuardrailEvent(phase=LLMGuardrailPhase.INPUT, messages=history)
        decision = guard(event)
        assert decision.action == GuardrailAction.BLOCK

    def test_input_tool_calls_counted(self):
        from railtracks.llm.content import ToolCall, ToolCalls

        guard = InputLengthGuard(max_chars=1000)
        calls = ToolCalls(
            [ToolCall(identifier="1", name="search", arguments={"q": "weather"})],
            text="Looking it up.",
        )
        history = MessageHistory([UserMessage("weather?"), AssistantMessage(calls)])
        event = LLMGuardrailEvent(phase=LLMGuardrailPhase.INPUT, messages=history)
        decision = guard(event)
        assert decision.action == GuardrailAction.ALLOW
        # Must include the call name and the json of arguments
        assert decision.meta["total_chars"] > len("weather?") + len("Looking it up.")

    def test_output_tool_calls(self):
        from railtracks.llm.content import ToolCall, ToolCalls

        guard = OutputLengthGuard(max_chars=1000)
        calls = ToolCalls(
            [ToolCall(identifier="1", name="search", arguments={"q": "x"})],
            text="ok",
        )
        event = LLMGuardrailEvent(
            phase=LLMGuardrailPhase.OUTPUT,
            messages=MessageHistory([UserMessage("hi")]),
            output_message=AssistantMessage(calls),
        )
        decision = guard(event)
        assert decision.action == GuardrailAction.ALLOW
        assert decision.meta["total_chars"] > 2  # more than just "ok"

    def test_output_basemodel(self):
        from pydantic import BaseModel

        class Answer(BaseModel):
            city: str
            temp: int

        guard = OutputLengthGuard(max_chars=1000)
        answer = Answer(city="Pune", temp=28)
        event = LLMGuardrailEvent(
            phase=LLMGuardrailPhase.OUTPUT,
            messages=MessageHistory([UserMessage("hi")]),
            output_message=AssistantMessage(answer),
        )
        decision = guard(event)
        assert decision.action == GuardrailAction.ALLOW
        # model_dump_json is longer than 0
        assert decision.meta["total_chars"] > 0

        # blocked when over limit
        guard_small = OutputLengthGuard(max_chars=5)
        decision_small = guard_small(event)
        assert decision_small.action == GuardrailAction.BLOCK


class TestMessageCharCountHelper:
    """Direct unit tests for the shared helper."""

    def test_none(self):
        from railtracks.prebuilt.guardrails._length import message_char_count

        assert message_char_count(None) == 0

    def test_str(self):
        from railtracks.prebuilt.guardrails._length import message_char_count

        assert message_char_count("hello") == 5

    def test_tool_response(self):
        from railtracks.llm.content import ToolResponse
        from railtracks.prebuilt.guardrails._length import message_char_count

        tr = ToolResponse(identifier="1", name="t", result="abc")
        assert message_char_count(tr) == 3

    def test_tool_calls(self):
        from railtracks.llm.content import ToolCall, ToolCalls
        from railtracks.prebuilt.guardrails._length import message_char_count

        calls = ToolCalls(
            [ToolCall(identifier="1", name="search", arguments={"q": "hi"})],
            text="ok",
        )
        count = message_char_count(calls)
        assert count == len("ok") + len("search") + len('{"q": "hi"}')

    def test_basemodel(self):
        from pydantic import BaseModel
        from railtracks.prebuilt.guardrails._length import message_char_count

        class M(BaseModel):
            x: int

        assert message_char_count(M(x=1)) == len(M(x=1).model_dump_json())

    def test_other(self):
        from railtracks.prebuilt.guardrails._length import message_char_count

        assert message_char_count(123) == len("123")
