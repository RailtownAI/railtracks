"""Tests for PIIRedactOutputGuard."""

from __future__ import annotations

import pytest

from railtracks.guardrails.core.decision import GuardrailAction
from railtracks.guardrails.core.event import LLMGuardrailEvent, LLMGuardrailPhase
from railtracks.guardrails.llm import PIIRedactOutputGuard
from railtracks.llm import MessageHistory
from railtracks.llm.message import AssistantMessage, UserMessage


def _make_output_event(output_content: str) -> LLMGuardrailEvent:
    return LLMGuardrailEvent(
        phase=LLMGuardrailPhase.OUTPUT,
        messages=MessageHistory([UserMessage("hi")]),
        output_message=AssistantMessage(output_content),
    )


@pytest.fixture
def guard() -> PIIRedactOutputGuard:
    return PIIRedactOutputGuard()


class TestAllow:
    def test_clean_output(self, guard: PIIRedactOutputGuard) -> None:
        event = _make_output_event("Here is your answer.")
        decision = guard(event)
        assert decision.action == GuardrailAction.ALLOW

    def test_no_output_message(self, guard: PIIRedactOutputGuard) -> None:
        event = LLMGuardrailEvent(
            phase=LLMGuardrailPhase.OUTPUT,
            messages=MessageHistory([UserMessage("hi")]),
            output_message=None,
        )
        decision = guard(event)
        assert decision.action == GuardrailAction.ALLOW


class TestTransformOutput:
    def test_email_in_output(self, guard: PIIRedactOutputGuard) -> None:
        event = _make_output_event("Contact alice@example.com for help.")
        decision = guard(event)
        assert decision.action == GuardrailAction.TRANSFORM
        assert decision.output_message is not None
        assert "[EMAIL_ADDRESS]" in decision.output_message.content
        assert "alice@example.com" not in decision.output_message.content

    def test_ssn_in_output(self, guard: PIIRedactOutputGuard) -> None:
        event = _make_output_event("Your SSN is 123-45-6789.")
        decision = guard(event)
        assert decision.action == GuardrailAction.TRANSFORM
        assert "[US_SSN]" in decision.output_message.content


class TestMetaSummary:
    def test_meta_present(self, guard: PIIRedactOutputGuard) -> None:
        event = _make_output_event("Email: alice@example.com")
        decision = guard(event)
        assert decision.meta is not None
        assert "redacted_entities" in decision.meta
        entities = decision.meta["redacted_entities"]
        assert any(e["entity_type"] == "EMAIL_ADDRESS" for e in entities)

    def test_meta_has_no_messages_affected(self, guard: PIIRedactOutputGuard) -> None:
        event = _make_output_event("Email: alice@example.com")
        decision = guard(event)
        assert "messages_affected" not in decision.meta

    def test_meta_does_not_contain_raw_value(
        self, guard: PIIRedactOutputGuard
    ) -> None:
        event = _make_output_event("SSN: 123-45-6789")
        decision = guard(event)
        meta_str = str(decision.meta)
        assert "123-45-6789" not in meta_str


class TestNonStringOutput:
    def test_non_string_content_skipped(self, guard: PIIRedactOutputGuard) -> None:
        from railtracks.llm.message import AssistantMessage as AM

        msg = AM(content=[])
        event = LLMGuardrailEvent(
            phase=LLMGuardrailPhase.OUTPUT,
            messages=MessageHistory([UserMessage("hi")]),
            output_message=msg,
        )
        decision = guard(event)
        assert decision.action == GuardrailAction.ALLOW
