import asyncio

import pytest
import railtracks as rt
from railtracks.exceptions import NodeCreationError


def _agent(mock_llm, response: str):
    """Builds a terminal agent whose mocked model streams `response` char-by-char."""
    return rt.agent_node(
        name="Streamer",
        system_message="stream",
        llm=mock_llm(response),
    )


@pytest.mark.asyncio
async def test_astream_yields_chunks_and_result(mock_llm):
    """Iterating the stream yields the token chunks; .result exposes the final Response."""
    agent = _agent(mock_llm, "Echo")

    stream = rt.astream(agent, user_input="go")
    chunks = [chunk async for chunk in stream]

    # the mock model streams one character per chunk
    assert chunks == ["E", "c", "h", "o"]
    assert "".join(chunks) == "Echo"
    assert stream.result.text == "Echo"


@pytest.mark.asyncio
async def test_astream_await_returns_result(mock_llm):
    """Awaiting the stream (without iterating) drains it and returns the final Response."""
    agent = _agent(mock_llm, "Hello")

    final = await rt.astream(agent, user_input="go")

    assert final.text == "Hello"


@pytest.mark.asyncio
async def test_astream_early_break_still_resolves_result(mock_llm):
    """Breaking out early does not cancel the run; awaiting afterwards yields the full result."""
    agent = _agent(mock_llm, "abcdef")

    stream = rt.astream(agent, user_input="go")
    seen = []
    async for chunk in stream:
        seen.append(chunk)
        break

    assert seen == ["a"]
    # the underlying run always completes; the buffered result is the whole message
    final = await stream
    assert final.text == "abcdef"


@pytest.mark.asyncio
async def test_astream_nested_in_function_node(mock_llm):
    """rt.astream is used inside a @function_node; the outer node is driven by rt.call."""
    agent = _agent(mock_llm, "nested")

    @rt.function_node
    async def head(prompt: str) -> str:
        collected = []
        stream = rt.astream(agent, user_input=prompt)
        async for chunk in stream:
            collected.append(chunk)
        # the streamed chunks reconstruct the message, and .result carries the Response
        assert "".join(collected) == stream.result.text
        return stream.result.text

    result = await rt.call(head, "go")
    assert result == "nested"


@pytest.mark.asyncio
async def test_astream_two_concurrent_streams_are_isolated(mock_llm):
    """Two concurrent streams each receive only their own chunks (queues are per-call)."""
    agent_a = _agent(mock_llm, "AAAA")
    agent_b = _agent(mock_llm, "BBBB")

    async def drain(stream):
        return [chunk async for chunk in stream]

    with rt.Session():
        a = rt.astream(agent_a, user_input="go")
        b = rt.astream(agent_b, user_input="go")
        a_chunks, b_chunks = await asyncio.gather(drain(a), drain(b))

    assert a_chunks == ["A", "A", "A", "A"]
    assert b_chunks == ["B", "B", "B", "B"]
    assert a.result.text == "AAAA"
    assert b.result.text == "BBBB"


@pytest.mark.asyncio
async def test_astream_rejects_non_agent_node():
    """rt.astream only accepts agent nodes; a function/tool node raises before running."""

    @rt.function_node
    async def head(prompt: str) -> str:
        return prompt

    with pytest.raises(NodeCreationError, match="only supports agent nodes"):
        rt.astream(head, "go")
