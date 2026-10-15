"""Unit tests for InputLengthGuard and OutputLengthGuard."""

from __future__ import annotations

import pytest
from pydantic import BaseModel
from railtracks.guardrails.core.decision import GuardrailAction
from railtracks.guardrails.core.event import LLMGuardrailEvent, LLMGuardrailPhase
from railtracks.llm import MessageHistory, ToolMessage, ToolResponse, UserMessage
from railtracks.llm.content import ToolCall, ToolCalls
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
# Non-string content (regression: #1689)
# ---------------------------------------------------------------------------


class _Structured(BaseModel):
    """A structured-output assistant reply."""

    answer: str
    score: int


def _tool_history() -> MessageHistory:
    return MessageHistory(
        [
            UserMessage("What is the weather?"),
            ToolMessage(ToolResponse(identifier="1", name="weather", result="15C")),
        ]
    )


class TestNonStringContent:
    """Length guards must measure tool and structured content, not raise (#1689)."""

    def test_input_guard_counts_a_tool_response(self):
        guard = InputLengthGuard(max_chars=1000)
        event = LLMGuardrailEvent(
            phase=LLMGuardrailPhase.INPUT, messages=_tool_history()
        )
        decision = guard(event)
        assert decision.action == GuardrailAction.ALLOW
        assert decision.meta["total_chars"] > 0

    def test_input_guard_counts_a_tool_call_turn(self):
        guard = InputLengthGuard(max_chars=1000)
        calls = ToolCalls(
            [ToolCall(identifier="1", name="weather", arguments={"city": "Paris"})],
            text="Let me look that up.",
        )
        history = MessageHistory([UserMessage("hi"), AssistantMessage(calls)])
        decision = guard(
            LLMGuardrailEvent(phase=LLMGuardrailPhase.INPUT, messages=history)
        )
        assert decision.action == GuardrailAction.ALLOW
        assert decision.meta["total_chars"] >= len("Let me look that up.")

    def test_input_guard_counts_a_structured_output(self):
        guard = InputLengthGuard(max_chars=1000)
        history = MessageHistory(
            [UserMessage("hi"), AssistantMessage(_Structured(answer="ok", score=3))]
        )
        decision = guard(
            LLMGuardrailEvent(phase=LLMGuardrailPhase.INPUT, messages=history)
        )
        assert decision.action == GuardrailAction.ALLOW

    def test_input_guard_still_blocks_an_oversized_tool_history(self):
        guard = InputLengthGuard(max_chars=10)
        event = LLMGuardrailEvent(
            phase=LLMGuardrailPhase.INPUT, messages=_tool_history()
        )
        decision = guard(event)
        assert decision.action == GuardrailAction.BLOCK

    def test_output_guard_counts_a_structured_reply(self):
        guard = OutputLengthGuard(max_chars=1000)
        event = LLMGuardrailEvent(
            phase=LLMGuardrailPhase.OUTPUT,
            messages=MessageHistory([UserMessage("hi")]),
            output_message=AssistantMessage(_Structured(answer="ok", score=3)),
        )
        decision = guard(event)
        assert decision.action == GuardrailAction.ALLOW
        assert decision.meta["total_chars"] > 0

    def test_output_guard_counts_a_tool_call_turn(self):
        guard = OutputLengthGuard(max_chars=1000)
        event = LLMGuardrailEvent(
            phase=LLMGuardrailPhase.OUTPUT,
            messages=MessageHistory([UserMessage("hi")]),
            output_message=AssistantMessage(
                ToolCalls(
                    [ToolCall(identifier="1", name="weather", arguments={})],
                    text="Looking it up.",
                )
            ),
        )
        decision = guard(event)
        assert decision.action == GuardrailAction.ALLOW
        assert decision.meta["total_chars"] >= len("Looking it up.")
