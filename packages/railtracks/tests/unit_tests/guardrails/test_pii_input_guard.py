"""Tests for PIIRedactInputGuard."""

from __future__ import annotations

import pytest

from railtracks.guardrails.core.decision import GuardrailAction
from railtracks.guardrails.core.event import LLMGuardrailEvent, LLMGuardrailPhase
from railtracks.guardrails.llm import (
    PIICustomPattern,
    PIIEntity,
    PIIRedactConfig,
    PIIRedactInputGuard,
)
from railtracks.llm import MessageHistory
from railtracks.llm.message import (
    AssistantMessage,
    Role,
    SystemMessage,
    UserMessage,
)


def _make_input_event(messages: MessageHistory) -> LLMGuardrailEvent:
    return LLMGuardrailEvent(
        phase=LLMGuardrailPhase.INPUT,
        messages=messages,
    )


@pytest.fixture
def guard() -> PIIRedactInputGuard:
    return PIIRedactInputGuard()


class TestAllow:
    def test_clean_history(self, guard: PIIRedactInputGuard) -> None:
        event = _make_input_event(MessageHistory([UserMessage("Hello world")]))
        decision = guard(event)
        assert decision.action == GuardrailAction.ALLOW

    def test_empty_history(self, guard: PIIRedactInputGuard) -> None:
        event = _make_input_event(MessageHistory())
        decision = guard(event)
        assert decision.action == GuardrailAction.ALLOW


class TestTransformUserMessage:
    def test_email_in_user_message(self, guard: PIIRedactInputGuard) -> None:
        event = _make_input_event(
            MessageHistory([UserMessage("My email is alice@example.com")])
        )
        decision = guard(event)
        assert decision.action == GuardrailAction.TRANSFORM
        assert decision.messages is not None
        assert len(decision.messages) == 1
        assert "[EMAIL_ADDRESS]" in decision.messages[0].content

    def test_phone_in_user_message(self, guard: PIIRedactInputGuard) -> None:
        event = _make_input_event(
            MessageHistory([UserMessage("Call me at +1 555-867-5309")])
        )
        decision = guard(event)
        assert decision.action == GuardrailAction.TRANSFORM
        assert "[PHONE_NUMBER]" in decision.messages[0].content


class TestTransformSystemMessage:
    def test_pii_in_system_message(self, guard: PIIRedactInputGuard) -> None:
        event = _make_input_event(
            MessageHistory([SystemMessage("Admin email: admin@corp.com")])
        )
        decision = guard(event)
        assert decision.action == GuardrailAction.TRANSFORM
        assert "[EMAIL_ADDRESS]" in decision.messages[0].content


class TestSkippedRoles:
    def test_assistant_message_not_touched(self, guard: PIIRedactInputGuard) -> None:
        msg = AssistantMessage("Contact alice@example.com")
        event = _make_input_event(MessageHistory([msg]))
        decision = guard(event)
        assert decision.action == GuardrailAction.ALLOW


class TestMetaSummary:
    def test_meta_contains_redacted_entities(
        self, guard: PIIRedactInputGuard
    ) -> None:
        event = _make_input_event(
            MessageHistory([UserMessage("SSN: 123-45-6789")])
        )
        decision = guard(event)
        assert decision.meta is not None
        assert "redacted_entities" in decision.meta
        entities = decision.meta["redacted_entities"]
        assert any(e["entity_type"] == "US_SSN" for e in entities)

    def test_meta_has_messages_affected(self, guard: PIIRedactInputGuard) -> None:
        event = _make_input_event(
            MessageHistory([
                UserMessage("SSN: 123-45-6789"),
                UserMessage("Hello world"),
            ])
        )
        decision = guard(event)
        assert decision.meta is not None
        assert decision.meta["messages_affected"] == 1

    def test_meta_does_not_contain_raw_value(
        self, guard: PIIRedactInputGuard
    ) -> None:
        event = _make_input_event(
            MessageHistory([UserMessage("SSN: 123-45-6789")])
        )
        decision = guard(event)
        meta_str = str(decision.meta)
        assert "123-45-6789" not in meta_str


class TestMultipleMessages:
    def test_pii_across_several_messages(self, guard: PIIRedactInputGuard) -> None:
        event = _make_input_event(
            MessageHistory([
                UserMessage("Email: alice@example.com"),
                SystemMessage("Server: 192.168.1.1"),
                UserMessage("Clean message"),
            ])
        )
        decision = guard(event)
        assert decision.action == GuardrailAction.TRANSFORM
        assert decision.messages is not None
        assert len(decision.messages) == 3
        assert "[EMAIL_ADDRESS]" in decision.messages[0].content
        assert "[IP_ADDRESS]" in decision.messages[1].content
        assert decision.messages[2].content == "Clean message"
        assert decision.meta["messages_affected"] == 2


class TestCustomPatternInGuard:
    def test_custom_pattern_fires(self) -> None:
        config = PIIRedactConfig(
            entities=[PIIEntity.EMAIL_ADDRESS],
            custom_patterns=[
                PIICustomPattern(name="EMPLOYEE_ID", regex=r"\bEMP-\d{6}\b"),
            ],
        )
        guard = PIIRedactInputGuard(config=config)
        event = _make_input_event(
            MessageHistory([UserMessage("Employee EMP-123456 here")])
        )
        decision = guard(event)
        assert decision.action == GuardrailAction.TRANSFORM
        assert "[EMPLOYEE_ID]" in decision.messages[0].content


class TestGuardName:
    def test_default_name(self) -> None:
        guard = PIIRedactInputGuard()
        assert guard.name == "PIIRedactInputGuard"

    def test_custom_name(self) -> None:
        guard = PIIRedactInputGuard(name="pii_input")
        assert guard.name == "pii_input"
