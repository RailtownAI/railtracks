"""Tests for LLMGuardrailEvent construction and validation."""

from __future__ import annotations

import pytest

from railtracks.guardrails.core import LLMGuardrailEvent, LLMGuardrailPhase


def test_event_rejects_invalid_messages_type():
    with pytest.raises(ValueError, match="messages"):
        LLMGuardrailEvent(phase=LLMGuardrailPhase.INPUT, messages="bad")  # type: ignore[arg-type]
