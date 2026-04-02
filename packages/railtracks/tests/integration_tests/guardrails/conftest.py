"""Fixtures for guardrails integration tests (no API keys)."""

from __future__ import annotations

import pytest

from railtracks.guardrails import GuardrailDecision, InputGuard, LLMGuardrailEvent


class _FixtureInputGuard(InputGuard):
    """Wrap a plain callable as an InputGuard for test fixtures."""

    def __init__(self, fn, name: str | None = None):
        super().__init__(name=name)
        self._fn = fn

    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision:
        return self._fn(event)


@pytest.fixture
def block_input() -> InputGuard:
    return _FixtureInputGuard(
        lambda _event: GuardrailDecision.block(
            reason="integration block",
            user_facing_message="blocked",
        )
    )


@pytest.fixture
def allow_input() -> InputGuard:
    return _FixtureInputGuard(lambda _event: GuardrailDecision.allow())
