"""Tests for InputGuard.evaluate() and OutputGuard.evaluate() convenience methods."""

from __future__ import annotations

import pytest

from railtracks.guardrails.core.decision import GuardrailAction
from railtracks.guardrails.core.event import LLMGuardrailEvent, LLMGuardrailPhase
from railtracks.guardrails.llm import (
    PIIEntity,
    PIIRedactConfig,
    PIIRedactInputGuard,
    PIIRedactOutputGuard,
)
from railtracks.llm import MessageHistory
from railtracks.llm.message import AssistantMessage, SystemMessage, UserMessage


@pytest.fixture
def input_guard() -> PIIRedactInputGuard:
    return PIIRedactInputGuard(
        config=PIIRedactConfig(entities=[PIIEntity.EMAIL_ADDRESS, PIIEntity.US_SSN])
    )


@pytest.fixture
def output_guard() -> PIIRedactOutputGuard:
    return PIIRedactOutputGuard(
        config=PIIRedactConfig(entities=[PIIEntity.EMAIL_ADDRESS, PIIEntity.US_SSN])
    )


class TestInputGuardEvaluateStr:
    def test_str_with_pii(self, input_guard: PIIRedactInputGuard) -> None:
        decision = input_guard.evaluate("my email is alice@example.com")
        assert decision.action == GuardrailAction.TRANSFORM
        assert decision.messages is not None
        assert "[EMAIL_ADDRESS]" in decision.messages[0].content

    def test_str_clean(self, input_guard: PIIRedactInputGuard) -> None:
        decision = input_guard.evaluate("hello world")
        assert decision.action == GuardrailAction.ALLOW


class TestInputGuardEvaluateMessage:
    def test_user_message(self, input_guard: PIIRedactInputGuard) -> None:
        decision = input_guard.evaluate(UserMessage("SSN: 123-45-6789"))
        assert decision.action == GuardrailAction.TRANSFORM
        assert "[US_SSN]" in decision.messages[0].content

    def test_system_message(self, input_guard: PIIRedactInputGuard) -> None:
        decision = input_guard.evaluate(SystemMessage("admin@corp.com is the admin"))
        assert decision.action == GuardrailAction.TRANSFORM


class TestInputGuardEvaluateMessageHistory:
    def test_history_with_pii(self, input_guard: PIIRedactInputGuard) -> None:
        history = MessageHistory([
            SystemMessage("You are helpful"),
            UserMessage("Email me at alice@example.com"),
        ])
        decision = input_guard.evaluate(history)
        assert decision.action == GuardrailAction.TRANSFORM
        assert len(decision.messages) == 2

    def test_history_clean(self, input_guard: PIIRedactInputGuard) -> None:
        history = MessageHistory([UserMessage("hello")])
        decision = input_guard.evaluate(history)
        assert decision.action == GuardrailAction.ALLOW


class TestInputGuardEvaluateEvent:
    def test_passthrough(self, input_guard: PIIRedactInputGuard) -> None:
        event = LLMGuardrailEvent(
            phase=LLMGuardrailPhase.INPUT,
            messages=MessageHistory([UserMessage("alice@example.com")]),
        )
        decision = input_guard.evaluate(event)
        assert decision.action == GuardrailAction.TRANSFORM


class TestInputGuardEvaluateTypeError:
    def test_invalid_type(self, input_guard: PIIRedactInputGuard) -> None:
        with pytest.raises(TypeError, match="Expected str"):
            input_guard.evaluate(42)  # type: ignore[arg-type]


class TestOutputGuardEvaluateStr:
    def test_str_with_pii(self, output_guard: PIIRedactOutputGuard) -> None:
        decision = output_guard.evaluate("Contact alice@example.com")
        assert decision.action == GuardrailAction.TRANSFORM
        assert decision.output_message is not None
        assert "[EMAIL_ADDRESS]" in decision.output_message.content

    def test_str_clean(self, output_guard: PIIRedactOutputGuard) -> None:
        decision = output_guard.evaluate("Here is your answer.")
        assert decision.action == GuardrailAction.ALLOW


class TestOutputGuardEvaluateMessage:
    def test_assistant_message(self, output_guard: PIIRedactOutputGuard) -> None:
        decision = output_guard.evaluate(
            AssistantMessage("Your SSN is 123-45-6789.")
        )
        assert decision.action == GuardrailAction.TRANSFORM
        assert "[US_SSN]" in decision.output_message.content


class TestOutputGuardEvaluateMessageHistory:
    def test_last_message_is_output(self, output_guard: PIIRedactOutputGuard) -> None:
        history = MessageHistory([
            UserMessage("What is my email?"),
            AssistantMessage("It is alice@example.com."),
        ])
        decision = output_guard.evaluate(history)
        assert decision.action == GuardrailAction.TRANSFORM
        assert "[EMAIL_ADDRESS]" in decision.output_message.content

    def test_single_message_history(self, output_guard: PIIRedactOutputGuard) -> None:
        history = MessageHistory([AssistantMessage("alice@example.com")])
        decision = output_guard.evaluate(history)
        assert decision.action == GuardrailAction.TRANSFORM

    def test_empty_history_raises(self, output_guard: PIIRedactOutputGuard) -> None:
        with pytest.raises(ValueError, match="empty"):
            output_guard.evaluate(MessageHistory())


class TestOutputGuardEvaluateEvent:
    def test_passthrough(self, output_guard: PIIRedactOutputGuard) -> None:
        event = LLMGuardrailEvent(
            phase=LLMGuardrailPhase.OUTPUT,
            messages=MessageHistory([UserMessage("hi")]),
            output_message=AssistantMessage("alice@example.com"),
        )
        decision = output_guard.evaluate(event)
        assert decision.action == GuardrailAction.TRANSFORM


class TestOutputGuardEvaluateTypeError:
    def test_invalid_type(self, output_guard: PIIRedactOutputGuard) -> None:
        with pytest.raises(TypeError, match="Expected str"):
            output_guard.evaluate(42)  # type: ignore[arg-type]
