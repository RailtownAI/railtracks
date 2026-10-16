"""Unit tests for InputLengthGuard and OutputLengthGuard."""

from __future__ import annotations

import pytest
from pydantic import BaseModel
from railtracks.guardrails.core.decision import GuardrailAction
from railtracks.guardrails.core.event import LLMGuardrailEvent, LLMGuardrailPhase
from railtracks.llm import MessageHistory, UserMessage
from railtracks.llm.content import ToolCall, ToolCalls, ToolResponse
from railtracks.llm.message import AssistantMessage, ToolMessage
from railtracks.prebuilt.guardrails import InputLengthGuard, OutputLengthGuard
from railtracks.prebuilt.guardrails._length import message_char_count

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
# message_char_count helper
# ---------------------------------------------------------------------------


class _SampleModel(BaseModel):
    answer: str
    score: int


class TestMessageCharCount:
    def test_none(self):
        assert message_char_count(None) == 0

    def test_str(self):
        assert message_char_count("hello") == 5

    def test_tool_response_str_result(self):
        tr = ToolResponse(identifier="1", name="weather", result="15C")
        assert message_char_count(tr) == 3

    def test_tool_response_bytes_result(self):
        tr = ToolResponse(identifier="1", name="bin", result=b"abc")
        assert message_char_count(tr) == 3

    def test_tool_calls_counts_text_name_and_args(self):
        calls = ToolCalls(
            [ToolCall(identifier="1", name="search", arguments={"q": "hi"})],
            text="Looking up.",
        )
        # "Looking up." (11) + "search" (6) + json.dumps({"q": "hi"})
        expected = 11 + 6 + len('{"q": "hi"}')
        assert message_char_count(calls) == expected

    def test_tool_calls_without_text(self):
        calls = ToolCalls([ToolCall(identifier="1", name="ping", arguments={})])
        expected = 0 + 4 + len("{}")
        assert message_char_count(calls) == expected

    def test_base_model(self):
        model = _SampleModel(answer="yes", score=1)
        assert message_char_count(model) == len(model.model_dump_json())

    def test_fallback_str(self):
        assert message_char_count(42) == len("42")


# ---------------------------------------------------------------------------
# Non-string content through the guards (regression for #1689)
# ---------------------------------------------------------------------------


class TestInputLengthGuardNonStringContent:
    def test_tool_message_under_limit_is_allowed(self):
        history = MessageHistory(
            [
                UserMessage("What is the weather?"),
                ToolMessage(ToolResponse(identifier="1", name="weather", result="15C")),
            ]
        )
        event = LLMGuardrailEvent(phase=LLMGuardrailPhase.INPUT, messages=history)
        decision = InputLengthGuard(max_chars=1000)(event)
        assert decision.action == GuardrailAction.ALLOW
        # "What is the weather?" (20) + "15C" (3)
        assert decision.meta["total_chars"] == 23

    def test_tool_message_over_limit_is_blocked(self):
        history = MessageHistory(
            [
                UserMessage("hi"),
                ToolMessage(
                    ToolResponse(identifier="1", name="weather", result="x" * 50)
                ),
            ]
        )
        event = LLMGuardrailEvent(phase=LLMGuardrailPhase.INPUT, messages=history)
        decision = InputLengthGuard(max_chars=20)(event)
        assert decision.action == GuardrailAction.BLOCK
        assert decision.meta["total_chars"] == 2 + 50

    def test_tool_calls_turn_counts_name_and_arguments(self):
        calls = ToolCalls(
            [ToolCall(identifier="1", name="search", arguments={"q": "hi"})],
            text="ok",
        )
        history = MessageHistory([UserMessage("go"), AssistantMessage(calls)])
        event = LLMGuardrailEvent(phase=LLMGuardrailPhase.INPUT, messages=history)
        decision = InputLengthGuard(max_chars=1000)(event)
        assert decision.action == GuardrailAction.ALLOW
        expected = 2 + 2 + 6 + len('{"q": "hi"}')
        assert decision.meta["total_chars"] == expected


class TestOutputLengthGuardNonStringContent:
    def test_tool_calls_output_under_limit(self):
        calls = ToolCalls(
            [ToolCall(identifier="1", name="ping", arguments={})],
            text="done",
        )
        event = LLMGuardrailEvent(
            phase=LLMGuardrailPhase.OUTPUT,
            messages=MessageHistory([UserMessage("prompt")]),
            output_message=AssistantMessage(calls),
        )
        decision = OutputLengthGuard(max_chars=100)(event)
        assert decision.action == GuardrailAction.ALLOW
        expected = 4 + 4 + len("{}")
        assert decision.meta["total_chars"] == expected

    def test_base_model_output_under_limit(self):
        model = _SampleModel(answer="yes", score=1)
        event = LLMGuardrailEvent(
            phase=LLMGuardrailPhase.OUTPUT,
            messages=MessageHistory([UserMessage("prompt")]),
            output_message=AssistantMessage(model),
        )
        decision = OutputLengthGuard(max_chars=1000)(event)
        assert decision.action == GuardrailAction.ALLOW
        assert decision.meta["total_chars"] == len(model.model_dump_json())

    def test_base_model_output_over_limit_is_blocked(self):
        model = _SampleModel(answer="x" * 200, score=1)
        event = LLMGuardrailEvent(
            phase=LLMGuardrailPhase.OUTPUT,
            messages=MessageHistory([UserMessage("prompt")]),
            output_message=AssistantMessage(model),
        )
        decision = OutputLengthGuard(max_chars=50)(event)
        assert decision.action == GuardrailAction.BLOCK
