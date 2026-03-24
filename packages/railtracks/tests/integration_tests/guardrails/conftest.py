"""Fixtures for guardrails integration tests (no API keys)."""

from __future__ import annotations

from typing import Callable

import pytest

from railtracks.guardrails import GuardrailDecision, LLMGuardrailEvent


@pytest.fixture
def block_input() -> Callable[[LLMGuardrailEvent], GuardrailDecision]:
    def _block(_event: LLMGuardrailEvent) -> GuardrailDecision:
        return GuardrailDecision.block(
            reason="integration block",
            user_facing_message="blocked",
        )

    return _block


@pytest.fixture
def allow_input() -> Callable[[LLMGuardrailEvent], GuardrailDecision]:
    def _allow(_event: LLMGuardrailEvent) -> GuardrailDecision:
        return GuardrailDecision.allow()

    return _allow
