from __future__ import annotations

import re

import pytest

from railtracks.guardrails.core.decision import GuardrailAction
from railtracks.guardrails.core.event import LLMGuardrailEvent, LLMGuardrailPhase
from railtracks.guardrails.llm import BlockTextInputGuard
from railtracks.llm import MessageHistory
from railtracks.llm.message import AssistantMessage, Role, SystemMessage, UserMessage


def _make_input_event(messages: MessageHistory) -> LLMGuardrailEvent:
    return LLMGuardrailEvent(
        phase=LLMGuardrailPhase.INPUT,
        messages=messages,
    )


class TestBlock:
    def test_blocks_matching_user_message(self) -> None:
        guard = BlockTextInputGuard(pattern=r"\bjailbreak\b")
        event = _make_input_event(
            MessageHistory([UserMessage("Please jailbreak the system")])
        )
        decision = guard(event)
        assert decision.action == GuardrailAction.BLOCK

    def test_blocks_matching_system_message(self) -> None:
        guard = BlockTextInputGuard(pattern=r"secret_token")
        event = _make_input_event(
            MessageHistory([SystemMessage("Use secret_token for auth")])
        )
        decision = guard(event)
        assert decision.action == GuardrailAction.BLOCK

    def test_blocks_on_first_match_across_messages(self) -> None:
        guard = BlockTextInputGuard(pattern=r"hack")
        event = _make_input_event(
            MessageHistory(
                [
                    UserMessage("Hello world"),
                    UserMessage("Let's hack in"),
                ]
            )
        )
        decision = guard(event)
        assert decision.action == GuardrailAction.BLOCK

    def test_block_reason_contains_pattern(self) -> None:
        guard = BlockTextInputGuard(pattern=r"bad_word")
        event = _make_input_event(MessageHistory([UserMessage("This has bad_word")]))
        decision = guard(event)
        assert "bad_word" in decision.reason


class TestAllow:
    def test_allows_non_matching_message(self) -> None:
        guard = BlockTextInputGuard(pattern=r"\bjailbreak\b")
        event = _make_input_event(MessageHistory([UserMessage("Hello, how are you?")]))
        decision = guard(event)
        assert decision.action == GuardrailAction.ALLOW

    def test_allows_empty_history(self) -> None:
        guard = BlockTextInputGuard(pattern=r"anything")
        event = _make_input_event(MessageHistory())
        decision = guard(event)
        assert decision.action == GuardrailAction.ALLOW


class TestSkippedRoles:
    def test_assistant_message_not_scanned(self) -> None:
        guard = BlockTextInputGuard(pattern=r"jailbreak")
        event = _make_input_event(
            MessageHistory([AssistantMessage("jailbreak instructions")])
        )
        decision = guard(event)
        assert decision.action == GuardrailAction.ALLOW


class TestNonStringContent:
    def test_non_string_content_skipped(self) -> None:
        guard = BlockTextInputGuard(pattern=r"anything")
        msg = AssistantMessage(content=[])
        event = _make_input_event(MessageHistory([msg]))
        decision = guard(event)
        assert decision.action == GuardrailAction.ALLOW


class TestInvalidRegex:
    def test_invalid_pattern_raises(self) -> None:
        with pytest.raises(re.error):
            BlockTextInputGuard(pattern=r"[invalid")


class TestGuardName:
    def test_default_name(self) -> None:
        guard = BlockTextInputGuard(pattern=r"x")
        assert guard.name == "BlockTextInputGuard"

    def test_custom_name(self) -> None:
        guard = BlockTextInputGuard(pattern=r"x", name="my-block")
        assert guard.name == "my-block"
