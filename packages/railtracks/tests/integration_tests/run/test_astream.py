import asyncio

import pytest
import railtracks as rt
from pydantic import BaseModel
from railtracks.context.central import is_context_present
from railtracks.exceptions import GlobalTimeOutError, LLMError, NodeCreationError
from railtracks.llm import ToolCall
from railtracks.llm.providers import ModelProvider


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


# ---------------------------------------------------------------------------
# rt.astream + tool-calling / structured agents. The `_astream.py` docstring claims
# support for "terminal, tool-calling, and structured agents", but until the MockLLM
# fixture grew `_astream_chat_with_tools`/`_astream_structured` overrides only the
# terminal case above was ever actually exercised.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_astream_tool_calling_agent_streams_final_reply(mock_llm):
    """A tool-calling agent streamed via rt.astream: the tool-request turn yields no
    chunks (tool calls aren't streamable text), the post-tool-call turn streams the
    final reply char-by-char, and `.result` reflects it."""

    def secret_phrase():
        return "Constantinople"

    llm = mock_llm(
        requested_tool_calls=[
            ToolCall(name="secret_phrase", identifier="id_42424242", arguments={})
        ]
    )
    agent = rt.agent_node(
        name="ToolStreamer",
        tool_nodes={rt.function_node(secret_phrase)},
        system_message="you can call tools",
        llm=llm,
    )

    stream = rt.astream(agent, user_input="what is the secret phrase?")
    chunks = [chunk async for chunk in stream]

    assert "".join(chunks) == stream.result.text
    assert "Constantinople" in stream.result.text


@pytest.mark.asyncio
async def test_astream_structured_agent_yields_final_result(mock_llm):
    """A structured-output agent streamed via rt.astream: `.result.content` is the
    parsed schema instance."""

    class Answer(BaseModel):
        value: int

    llm = mock_llm(custom_response='{"value": 42}')
    agent = rt.agent_node(
        name="StructuredStreamer",
        output_schema=Answer,
        system_message="return structured output",
        llm=llm,
    )

    stream = rt.astream(agent, user_input="go")
    chunks = [chunk async for chunk in stream]

    assert chunks == []
    assert isinstance(stream.result.content, Answer)
    assert stream.result.content.value == 42


@pytest.mark.asyncio
async def test_astream_tool_calling_blacklisted_provider_falls_back_buffered(mock_llm):
    """A blacklisted provider (tool calling + streaming unsupported together) still
    succeeds under rt.astream: the call falls back to buffered, so no chunks are
    emitted, but `.result` is unaffected."""

    class BlacklistedProviderLLM(mock_llm):
        def model_provider(self):
            return ModelProvider.ANTHROPIC

    def secret_phrase():
        return "Constantinople"

    llm = BlacklistedProviderLLM(
        requested_tool_calls=[
            ToolCall(name="secret_phrase", identifier="id_42424242", arguments={})
        ]
    )
    agent = rt.agent_node(
        name="BlacklistedToolStreamer",
        tool_nodes={rt.function_node(secret_phrase)},
        system_message="you can call tools",
        llm=llm,
    )

    stream = rt.astream(agent, user_input="what is the secret phrase?")
    chunks = [chunk async for chunk in stream]

    # no chunks: the tool-calling call fell back to a buffered (non-streamed) response
    assert chunks == []
    assert "Constantinople" in stream.result.text


# ---------------------------------------------------------------------------
# Stream failure / timeout / session-lifecycle. None of this was covered before:
# a mid-stream exception, a timed-out run, accessing `.result` too early, and the
# session that `rt.astream` opens for itself when called outside any `with
# rt.Session()` block.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_astream_mid_stream_node_failure_propagates_and_cleans_up(mock_llm):
    """If the node raises partway through streaming, the exception propagates out
    of the `async for` loop (matching rt.call), and the completion subscriber is
    unsubscribed (no dangling subscription left behind)."""

    class _FailingLLM(mock_llm):
        async def _astream_chat(self, messages, **kwargs):
            yield "a"
            yield "b"
            raise RuntimeError("boom mid-stream")

    agent = rt.agent_node(name="Failer", system_message="stream", llm=_FailingLLM())

    with rt.Session():
        stream = rt.astream(agent, user_input="go")
        seen = []
        # the model's raw error is wrapped as LLMError by the tool-calling loop
        # (llm_helpers.llm_invoke), same as a non-streamed rt.call would see.
        with pytest.raises(LLMError, match="boom mid-stream"):
            async for chunk in stream:
                seen.append(chunk)

        assert seen == ["a", "b"]
        assert stream._sub_id is None

    # .result re-raises the same error rather than hanging or resetting state
    with pytest.raises(LLMError, match="boom mid-stream"):
        _ = stream.result


@pytest.mark.asyncio
async def test_astream_result_before_finished_raises_runtime_error(mock_llm):
    """Accessing `.result` before the stream has been consumed raises RuntimeError."""
    agent = _agent(mock_llm, "abc")

    with rt.Session():
        stream = rt.astream(agent, user_input="go")
        with pytest.raises(RuntimeError, match="has not finished"):
            _ = stream.result


@pytest.mark.asyncio
async def test_astream_owns_and_closes_its_own_session_on_success(mock_llm):
    """Calling rt.astream outside any `with rt.Session()` block opens one
    internally and closes it once the run completes successfully."""
    assert not is_context_present()
    agent = _agent(mock_llm, "abc")

    stream = rt.astream(agent, user_input="go")
    async for _ in stream:
        pass

    assert not is_context_present()


@pytest.mark.asyncio
async def test_astream_owns_and_closes_its_own_session_on_node_error(mock_llm):
    """The internally-opened session is closed even when the run raises."""

    class _FailingLLM(mock_llm):
        async def _astream_chat(self, messages, **kwargs):
            yield "a"
            raise RuntimeError("boom")

    assert not is_context_present()
    agent = rt.agent_node(name="Failer", system_message="stream", llm=_FailingLLM())

    stream = rt.astream(agent, user_input="go")
    with pytest.raises(LLMError, match="boom"):
        async for _ in stream:
            pass

    assert not is_context_present()


@pytest.mark.asyncio
async def test_astream_timeout_raises_global_timeout_error(mock_llm):
    """A run that exceeds the session's wall-clock timeout raises
    GlobalTimeOutError, and the stream is left in a finished/errored state."""

    class _SlowLLM(mock_llm):
        async def _astream_chat(self, messages, **kwargs):
            await asyncio.sleep(0.3)
            yield "too late"

    agent = rt.agent_node(name="Slow", system_message="stream", llm=_SlowLLM())

    with rt.Session(timeout=0.05):
        stream = rt.astream(agent, user_input="go")
        with pytest.raises(GlobalTimeOutError):
            async for _ in stream:
                pass

        # re-accessing .result re-raises the same timeout rather than hanging
        with pytest.raises(GlobalTimeOutError):
            _ = stream.result
