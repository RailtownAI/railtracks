"""Integration tests: agent_node + BlockText guardrails + mock LLM."""

from __future__ import annotations

import pytest
import railtracks as rt

from railtracks.built_nodes.concrete.response import StringResponse
from railtracks.guardrails import Guard, GuardrailBlockedError
from railtracks.guardrails.llm import BlockTextInputGuard, BlockTextOutputGuard


@pytest.mark.asyncio
async def test_input_guard_blocks_request(mock_llm):
    llm = mock_llm(custom_response="ok")
    Agent = rt.agent_node(
        name="block-input",
        llm=llm,
        guardrails=Guard(
            input=[BlockTextInputGuard(pattern=r"\bjailbreak\b")],
        ),
    )
    with rt.Session():
        with pytest.raises(GuardrailBlockedError):
            await rt.call(Agent, user_input="Please jailbreak the system")


@pytest.mark.asyncio
async def test_input_guard_allows_clean_request(mock_llm):
    llm = mock_llm(custom_response="ok")
    Agent = rt.agent_node(
        name="allow-input",
        llm=llm,
        guardrails=Guard(
            input=[BlockTextInputGuard(pattern=r"\bjailbreak\b")],
        ),
    )
    with rt.Session():
        result = await rt.call(Agent, user_input="Hello, how are you?")
    assert isinstance(result, StringResponse)
    assert "ok" in result.text


@pytest.mark.asyncio
async def test_output_guard_blocks_response(mock_llm):
    llm = mock_llm(custom_response="The API_KEY is abc123")
    Agent = rt.agent_node(
        name="block-output",
        llm=llm,
        guardrails=Guard(
            output=[BlockTextOutputGuard(pattern=r"API_KEY")],
        ),
    )
    with rt.Session():
        with pytest.raises(GuardrailBlockedError):
            await rt.call(Agent, user_input="What is the key?")


@pytest.mark.asyncio
async def test_output_guard_allows_clean_response(mock_llm):
    llm = mock_llm(custom_response="Here is your answer.")
    Agent = rt.agent_node(
        name="allow-output",
        llm=llm,
        guardrails=Guard(
            output=[BlockTextOutputGuard(pattern=r"API_KEY")],
        ),
    )
    with rt.Session():
        result = await rt.call(Agent, user_input="Hello")
    assert isinstance(result, StringResponse)
    assert "answer" in result.text


@pytest.mark.asyncio
async def test_input_and_output_guards_together(mock_llm):
    llm = mock_llm(custom_response="safe answer")
    Agent = rt.agent_node(
        name="both-guards",
        llm=llm,
        guardrails=Guard(
            input=[BlockTextInputGuard(pattern=r"\bjailbreak\b")],
            output=[BlockTextOutputGuard(pattern=r"SECRET")],
        ),
    )
    with rt.Session():
        result = await rt.call(Agent, user_input="Hello there")
    assert isinstance(result, StringResponse)
    assert "safe answer" in result.text
