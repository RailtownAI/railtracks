"""Unit tests for the prebuilt ContextInjection middleware:
`rt.prebuilt.middleware.ContextInjection`.

Wired directly via `.wrap(fake_call)`; the session-level behavior (injection
on/off via config, opt-in per agent) is covered by unit_tests/prompt and the
middleware integration tests.
"""

from __future__ import annotations

import pytest
import railtracks as rt
from railtracks.llm import MessageHistory, SystemMessage
from railtracks.middleware import Middleware
from railtracks.prebuilt.middleware import ContextInjection


def test_context_injection_is_a_plain_middleware():
    assert isinstance(ContextInjection(), Middleware)


@pytest.mark.asyncio
async def test_injects_active_session_context_before_calling_onward():
    seen = {}

    async def fake_call(message_history, schema, tools):
        seen["content"] = message_history[0].content
        return "response"

    history = MessageHistory([SystemMessage("You are helping {user_name}.")])

    with rt.Session(context={"user_name": "Alice"}):
        result = await ContextInjection().wrap(fake_call)(history, None, None)

    assert result == "response"
    assert seen["content"] == "You are helping Alice."


@pytest.mark.asyncio
async def test_no_session_is_a_noop():
    seen = {}

    async def fake_call(message_history, schema, tools):
        seen["content"] = message_history[0].content
        return "response"

    history = MessageHistory([SystemMessage("You are helping {user_name}.")])

    await ContextInjection().wrap(fake_call)(history, None, None)

    assert seen["content"] == "You are helping {user_name}."
