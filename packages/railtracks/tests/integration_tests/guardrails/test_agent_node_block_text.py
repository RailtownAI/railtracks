"""Integration tests: agent_node + BlockText guardrails + mock LLM."""

from __future__ import annotations

import pytest
import railtracks as rt
from railtracks.built_nodes.llm.response import StringResponse
from railtracks.guardrails import GuardrailBlockedError
from railtracks.prebuilt.guardrails import BlockTextInputGuard, BlockTextOutputGuard


@pytest.mark.asyncio
async def test_input_guard_blocks_request(mock_llm):
    llm = mock_llm(custom_response="ok")
    Agent = rt.agent_node(  # noqa: N806
        name="block-input",
        llm=llm,
        model_middleware=[BlockTextInputGuard(pattern=r"\bjailbreak\b")],
    )

    @rt.function_node
    async def entry(user_input):
        return await rt.call(Agent, user_input=user_input)

    with pytest.raises(GuardrailBlockedError):
        await rt.Flow("input_guard_blocks_request", entry).ainvoke(
            "Please jailbreak the system"
        )


@pytest.mark.asyncio
async def test_input_guard_allows_clean_request(mock_llm):
    llm = mock_llm(custom_response="ok")
    Agent = rt.agent_node(  # noqa: N806
        name="allow-input",
        llm=llm,
        model_middleware=[BlockTextInputGuard(pattern=r"\bjailbreak\b")],
    )

    @rt.function_node
    async def entry(user_input):
        return await rt.call(Agent, user_input=user_input)

    result = await rt.Flow("input_guard_allows_clean", entry).ainvoke(
        "Hello, how are you?"
    )
    assert isinstance(result, StringResponse)
    assert "ok" in result.text


@pytest.mark.asyncio
async def test_output_guard_blocks_response(mock_llm):
    llm = mock_llm(custom_response="The API_KEY is abc123")
    Agent = rt.agent_node(  # noqa: N806
        name="block-output",
        llm=llm,
        model_middleware=[BlockTextOutputGuard(pattern=r"API_KEY")],
    )

    @rt.function_node
    async def entry(user_input):
        return await rt.call(Agent, user_input=user_input)

    with pytest.raises(GuardrailBlockedError):
        await rt.Flow("output_guard_blocks_response", entry).ainvoke(
            "What is the key?"
        )


@pytest.mark.asyncio
async def test_output_guard_allows_clean_response(mock_llm):
    llm = mock_llm(custom_response="Here is your answer.")
    Agent = rt.agent_node(  # noqa: N806
        name="allow-output",
        llm=llm,
        model_middleware=[BlockTextOutputGuard(pattern=r"API_KEY")],
    )

    @rt.function_node
    async def entry(user_input):
        return await rt.call(Agent, user_input=user_input)

    result = await rt.Flow("output_guard_allows_clean", entry).ainvoke("Hello")
    assert isinstance(result, StringResponse)
    assert "answer" in result.text


@pytest.mark.asyncio
async def test_input_and_output_guards_together(mock_llm):
    llm = mock_llm(custom_response="safe answer")
    Agent = rt.agent_node(  # noqa: N806
        name="both-guards",
        llm=llm,
        model_middleware=[
            BlockTextInputGuard(pattern=r"\bjailbreak\b"),
            BlockTextOutputGuard(pattern=r"SECRET"),
        ],
    )

    @rt.function_node
    async def entry(user_input):
        return await rt.call(Agent, user_input=user_input)

    result = await rt.Flow("input_and_output_guards", entry).ainvoke("Hello there")
    assert isinstance(result, StringResponse)
    assert "safe answer" in result.text
