"""Fixtures for guardrails unit tests."""

from __future__ import annotations

import pytest

from railtracks.llm import MessageHistory, UserMessage


@pytest.fixture
def sample_history() -> MessageHistory:
    return MessageHistory([UserMessage("hello")])
