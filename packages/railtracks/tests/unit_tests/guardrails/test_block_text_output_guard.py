"""Tests for BlockTextOutputGuard."""

from __future__ import annotations

import re

import pytest

from railtracks.guardrails.core.decision import GuardrailAction
from railtracks.guardrails.core.event import LLMGuardrailEvent, LLMGuardrailPhase
from railtracks.guardrails.llm import BlockTextOutputGuard
from railtracks.llm import MessageHistory
from railtracks.llm.message import AssistantMessage, UserMessage


def _make_output_event(output_content: str) -> LLMGuardrailEvent:
    return LLMGuardrailEvent(
        phase=LLMGuardrailPhase.OUTPUT,
        messages=MessageHistory([UserMessage("hi")]),
        output_message=AssistantMessage(output_content),
    )


class TestBlock:
    def test_blocks_matching_output(self) -> None:
        guard = BlockTextOutputGuard(pattern=r"API_KEY")
        event = _make_output_event("Your API_KEY is abc123")
        decision = guard(event)
        assert decision.action == GuardrailAction.BLOCK

    def test_block_reason_does_not_leak_pattern(self) -> None:
        guard = BlockTextOutputGuard(pattern=r"SECRET")
        event = _make_output_event("The SECRET is here")
        decision = guard(event)
        assert decision.reason == "Output blocked: prohibited content detected."
        assert "SECRET" not in decision.reason


class TestAllow:
    def test_allows_non_matching_output(self) -> None:
        guard = BlockTextOutputGuard(pattern=r"API_KEY")
        event = _make_output_event("Here is your answer.")
        decision = guard(event)
        assert decision.action == GuardrailAction.ALLOW

    def test_allows_no_output_message(self) -> None:
        guard = BlockTextOutputGuard(pattern=r"anything")
        event = LLMGuardrailEvent(
            phase=LLMGuardrailPhase.OUTPUT,
            messages=MessageHistory([UserMessage("hi")]),
            output_message=None,
        )
        decision = guard(event)
        assert decision.action == GuardrailAction.ALLOW


class TestNonStringContent:
    def test_non_string_content_skipped(self) -> None:
        guard = BlockTextOutputGuard(pattern=r"anything")
        msg = AssistantMessage(content=[])
        event = LLMGuardrailEvent(
            phase=LLMGuardrailPhase.OUTPUT,
            messages=MessageHistory([UserMessage("hi")]),
            output_message=msg,
        )
        decision = guard(event)
        assert decision.action == GuardrailAction.ALLOW


class TestInvalidRegex:
    def test_invalid_pattern_raises(self) -> None:
        with pytest.raises(re.error):
            BlockTextOutputGuard(pattern=r"[invalid")


class TestGuardName:
    def test_default_name(self) -> None:
        guard = BlockTextOutputGuard(pattern=r"x")
        assert guard.name == "BlockTextOutputGuard"

    def test_custom_name(self) -> None:
        guard = BlockTextOutputGuard(pattern=r"x", name="my-block")
        assert guard.name == "my-block"
