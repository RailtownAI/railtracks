"""Integration tests for the V2 streaming path.

The V2 streaming path is activated by ``agent_node(stream=True)`` together with
a model whose ``stream=True``.  Internally it calls
``llm_stream_invoke_factory`` / ``ModelInvoker.invoke_stream`` /
``MiddlewareChain.run_stream``.

From the caller's perspective:
- ``rt.call(agent, user_input=...)`` still returns a ``StringResponse`` or
  ``StructuredResponse`` (unchanged public API).
- Real-time chunks are delivered to the ``broadcast_callback`` registered on
  the ``Session`` (or ``Flow``).

The ``AsyncStreamMockLLM`` defined in this file implements ``_achat`` /
``_astructured`` / ``_achat_with_tools`` as proper async generators so that
the ``ModelBase.achat`` / ``astructured`` / ``achat_with_tools`` wrappers
detect an async-gen and forward it as a streaming source.
"""

from __future__ import annotations

import json
from typing import AsyncGenerator, Generator, List, Literal, Type

import pytest
import railtracks as rt
from pydantic import BaseModel, Field
from railtracks.built_nodes.concrete.response import StringResponse, StructuredResponse
from railtracks.llm.message import AssistantMessage
from railtracks.llm.response import MessageInfo, Response

# ---------------------------------------------------------------------------
# AsyncStreamMockLLM
# ---------------------------------------------------------------------------


class AsyncStreamMockLLM(rt.llm.ModelBase):
    """Minimal streaming mock that yields individual characters then a Response.

    ``_achat``, ``_astructured``, and ``_achat_with_tools`` are all async
    generator functions so that ``ModelBase.achat`` / ``astructured`` /
    ``achat_with_tools`` detect the async-gen and wrap it as a streaming
    source — exactly the contract expected by ``ModelInvoker.invoke_stream``.
    """

    def __init__(
        self,
        response_text: str = "hello stream",
        stream: bool = True,
        requested_tool_calls: list[rt.llm.ToolCall] | None = None,
    ) -> None:
        super().__init__(stream=stream)
        self._response_text = response_text
        self._requested_tool_calls = requested_tool_calls
        self._mocked_message_info = MessageInfo(
            model_name="mock-stream",
            input_tokens=5,
            output_tokens=len(response_text),
        )

    # ------------------------------------------------------------------
    # Async streaming implementations
    # ------------------------------------------------------------------

    async def _achat(self, messages, **kwargs) -> AsyncGenerator[str | Response, None]:  # type: ignore[override]
        async def _gen():
            for char in self._response_text:
                yield char
            yield Response(
                message=AssistantMessage(self._response_text),
                message_info=self._mocked_message_info,
            )

        return _gen()

    async def _astructured(self, messages, schema, **kwargs) -> AsyncGenerator[str | Response, None]:  # type: ignore[override]
        async def _gen():
            # Build structured content and yield its JSON chars then the Response
            try:
                obj = schema(**json.loads(self._response_text))
                serialized = obj.model_dump_json()
            except Exception:
                serialized = self._response_text
                obj = None

            for char in serialized:
                yield char

            content = obj if obj is not None else self._response_text
            yield Response(
                message=AssistantMessage(content),
                message_info=self._mocked_message_info,
            )

        return _gen()

    async def _achat_with_tools(self, messages, tools, **kwargs) -> AsyncGenerator[str | Response, None]:  # type: ignore[override]
        """First call yields a tool-call Response; second call yields text + Response."""

        async def _tool_round():
            # If there are pending tool messages, yield a content response
            tool_results = [m for m in reversed(messages) if m.role == "tool"]
            if tool_results:
                final_text = ""
                for tr in reversed(tool_results):
                    final_text += f"Tool {tr.content.name} returned: '{tr.content.result}'\n"
                for char in final_text:
                    yield char
                yield Response(
                    message=AssistantMessage(final_text),
                    message_info=self._mocked_message_info,
                )
            else:
                # First round: yield a tool-call response (no text chunks)
                tool_calls = self._requested_tool_calls or []
                yield Response(
                    message=AssistantMessage(tool_calls),
                    message_info=self._mocked_message_info,
                )

        return _tool_round()

    # ------------------------------------------------------------------
    # Sync stubs (ABC requirement; not exercised by the V2 async path)
    # ------------------------------------------------------------------

    def _chat(self, messages, **kwargs) -> Response | Generator:  # type: ignore[override]
        raise NotImplementedError("sync path not used in V2 streaming tests")

    def _structured(self, messages, schema, **kwargs) -> Response | Generator:  # type: ignore[override]
        raise NotImplementedError("sync path not used in V2 streaming tests")

    def _chat_with_tools(self, messages, tools, **kwargs) -> Response | Generator:  # type: ignore[override]
        raise NotImplementedError("sync path not used in V2 streaming tests")

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    def model_name(self) -> str:
        return "mock-stream"

    def model_provider(self) -> str:
        return "mock"

    @classmethod
    def model_gateway(cls) -> str:
        return "mock"


# ---------------------------------------------------------------------------
# Structured output schema used by schema tests
# ---------------------------------------------------------------------------


class MySchema(BaseModel):
    answer: str = Field(description="The answer text.")
    score: int = Field(description="A numeric score.")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_v2_basic_streaming_broadcast_receives_chunks():
    """broadcast_callback receives each character of the response text."""
    received: list[str] = []

    def on_chunk(chunk: str) -> None:
        received.append(chunk)

    llm = AsyncStreamMockLLM("hello")
    agent = rt.agent_node(
        name="V2StreamAgent",
        system_message="You are a helpful assistant.",
        llm=llm,
        stream=True,
    )

    with rt.Session(broadcast_callback=on_chunk):
        response = await rt.call(agent, user_input="hi")

    assert isinstance(response, StringResponse)
    assert received == list("hello"), f"Expected individual chars, got {received}"


@pytest.mark.asyncio
async def test_v2_streaming_returns_string_response():
    """The return value is a StringResponse and .text equals the full assembled text."""
    llm = AsyncStreamMockLLM("hello stream")
    agent = rt.agent_node(
        name="V2StreamReturn",
        system_message="You are a helpful assistant.",
        llm=llm,
        stream=True,
    )

    with rt.Session():
        response = await rt.call(agent, user_input="hi")

    assert isinstance(response, StringResponse)
    assert response.text == "hello stream"


@pytest.mark.asyncio
async def test_v2_streaming_no_callback_still_returns_response():
    """Without a broadcast_callback the node still completes and returns StringResponse."""
    llm = AsyncStreamMockLLM("silent chunks")
    agent = rt.agent_node(
        name="V2StreamNoCallback",
        system_message="You are a helpful assistant.",
        llm=llm,
        stream=True,
    )

    with rt.Session():
        response = await rt.call(agent, user_input="hi")

    assert isinstance(response, StringResponse)
    assert response.text == "silent chunks"


@pytest.mark.asyncio
async def test_v2_streaming_async_callback():
    """An async broadcast_callback is also supported and fires for each chunk."""
    received: list[str] = []

    async def on_chunk_async(chunk: str) -> None:
        received.append(chunk)

    llm = AsyncStreamMockLLM("abc")
    agent = rt.agent_node(
        name="V2StreamAsyncCb",
        system_message="You are a helpful assistant.",
        llm=llm,
        stream=True,
    )

    with rt.Session(broadcast_callback=on_chunk_async):
        response = await rt.call(agent, user_input="hi")

    assert isinstance(response, StringResponse)
    assert received == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_v2_streaming_with_structured_output():
    """V2 streaming with output_schema returns a StructuredResponse."""
    payload = '{"answer": "forty-two", "score": 42}'
    llm = AsyncStreamMockLLM(payload)
    agent = rt.agent_node(
        name="V2StreamStructured",
        system_message="You are a helpful assistant.",
        llm=llm,
        output_schema=MySchema,
        stream=True,
    )

    chunks: list[str] = []

    def on_chunk(c: str) -> None:
        chunks.append(c)

    with rt.Session(broadcast_callback=on_chunk):
        response = await rt.call(agent, user_input="Give me structured output.")

    assert isinstance(response, StructuredResponse)
    assert isinstance(response.structured, MySchema)
    assert response.structured.answer == "forty-two"
    assert response.structured.score == 42
    # Chunks should be individual chars of the serialized JSON
    assert len(chunks) > 0


@pytest.mark.asyncio
async def test_v2_streaming_with_tool_node():
    """V2 streaming tool-calling: first round triggers a tool, second round streams text."""

    @rt.function_node
    def echo_tool(value: str) -> str:
        """Return the value verbatim.

        Args:
            value (str): The value to echo.

        Returns:
            str: The echoed value.
        """
        return value

    tool_call = rt.llm.ToolCall(
        name="echo_tool",
        identifier="id_tool_test",
        arguments={"value": "pong"},
    )

    llm = AsyncStreamMockLLM(
        response_text="result text",
        requested_tool_calls=[tool_call],
    )

    agent = rt.agent_node(
        name="V2StreamWithTool",
        system_message="You are a helpful assistant.",
        llm=llm,
        tool_nodes=[echo_tool],
        stream=True,
    )

    with rt.Session():
        response = await rt.call(agent, user_input="call the echo tool")

    assert isinstance(response, StringResponse)
    # The second LLM round assembles a response from tool result(s)
    assert isinstance(response.text, str)
    assert len(response.text) > 0


@pytest.mark.asyncio
async def test_v2_streaming_model_middleware_entry_gate_fires():
    """A model_middleware entry gate runs once per streaming round-trip."""
    gate_log: list[str] = []

    @rt.gate
    async def record_entry(*args, **kwargs):
        gate_log.append("entry")
        return args, kwargs

    llm = AsyncStreamMockLLM("hello gate")
    agent = rt.agent_node(
        name="V2StreamEntryGate",
        system_message="You are a helpful assistant.",
        llm=llm,
        model_middleware=rt.MiddlewareChain(entry_gate=[record_entry]),
        stream=True,
    )

    with rt.Session():
        await rt.call(agent, user_input="test entry gate")

    assert gate_log == ["entry"], f"Expected one entry gate call, got {gate_log}"


@pytest.mark.asyncio
async def test_v2_streaming_model_middleware_exit_gate_fires():
    """A model_middleware exit gate receives the terminal Response after streaming."""
    exit_log: list[str] = []

    @rt.gate
    async def record_exit(result):
        exit_log.append(result.message_info.model_name or "unknown")
        return result

    llm = AsyncStreamMockLLM("hello exit gate")
    agent = rt.agent_node(
        name="V2StreamExitGate",
        system_message="You are a helpful assistant.",
        llm=llm,
        model_middleware=rt.MiddlewareChain(exit_gate=[record_exit]),
        stream=True,
    )

    with rt.Session():
        await rt.call(agent, user_input="test exit gate")

    assert len(exit_log) == 1, f"Expected one exit gate call, got {exit_log}"
    assert exit_log[0] == "mock-stream"


# ---------------------------------------------------------------------------
# Flow.astream() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flow_astream_yields_chunks_then_response():
    """astream() yields str chunks first, then the terminal StringResponse."""
    llm = AsyncStreamMockLLM("hi")
    agent = rt.agent_node(
        name="AStreamBasic",
        system_message="You are a helpful assistant.",
        llm=llm,
        stream=True,
    )
    flow = rt.Flow(name="astream_basic", entry_point=agent)

    items: list = []
    async for item in flow.astream(user_input="go"):
        items.append(item)

    str_items = [i for i in items if isinstance(i, str)]
    response_items = [i for i in items if isinstance(i, StringResponse)]

    assert str_items == list("hi"), f"Expected chars of 'hi', got {str_items}"
    assert len(response_items) == 1
    assert response_items[0].text == "hi"
    # Terminal response is always last
    assert isinstance(items[-1], StringResponse)


@pytest.mark.asyncio
async def test_flow_astream_non_streaming_node_yields_only_response():
    """With a non-streaming node astream() yields only the terminal response."""
    from tests.conftest import MockLLM  # reuse existing non-streaming mock

    agent = rt.agent_node(
        name="AStreamNonStream",
        system_message="You are a helpful assistant.",
        llm=MockLLM(),
    )
    flow = rt.Flow(name="astream_ns", entry_point=agent)

    items: list = []
    async for item in flow.astream(user_input="hi"):
        items.append(item)

    assert len(items) == 1
    assert isinstance(items[0], StringResponse)


@pytest.mark.asyncio
async def test_flow_astream_structured_output():
    """astream() with output_schema yields JSON chunks then StructuredResponse."""
    payload = '{"answer": "forty-two", "score": 42}'
    llm = AsyncStreamMockLLM(payload)
    agent = rt.agent_node(
        name="AStreamStructured",
        system_message="You are a helpful assistant.",
        llm=llm,
        output_schema=MySchema,
        stream=True,
    )
    flow = rt.Flow(name="astream_structured", entry_point=agent)

    items: list = []
    async for item in flow.astream(user_input="structured"):
        items.append(item)

    str_items = [i for i in items if isinstance(i, str)]
    response_items = [i for i in items if isinstance(i, StructuredResponse)]

    assert len(str_items) > 0, "Expected JSON char chunks"
    assert len(response_items) == 1
    assert response_items[0].structured.answer == "forty-two"
    assert isinstance(items[-1], StructuredResponse)


@pytest.mark.asyncio
async def test_flow_astream_does_not_fire_broadcast_callback():
    """broadcast_callback on Flow is NOT fired when using astream()."""
    fired: list[str] = []

    llm = AsyncStreamMockLLM("abc")
    agent = rt.agent_node(
        name="AStreamNoCallback",
        system_message="You are a helpful assistant.",
        llm=llm,
        stream=True,
    )
    flow = rt.Flow(
        name="astream_no_cb",
        entry_point=agent,
        broadcast_callback=fired.append,
    )

    async for _ in flow.astream(user_input="go"):
        pass

    assert fired == [], f"broadcast_callback should not fire in astream(), got {fired}"


@pytest.mark.asyncio
async def test_flow_astream_assembled_text_matches_chunks():
    """The final StringResponse.text equals the concatenation of all str chunks."""
    text = "hello world"
    llm = AsyncStreamMockLLM(text)
    agent = rt.agent_node(
        name="AStreamAssemble",
        system_message="You are a helpful assistant.",
        llm=llm,
        stream=True,
    )
    flow = rt.Flow(name="astream_assemble", entry_point=agent)

    chunks: list[str] = []
    final = None
    async for item in flow.astream(user_input="go"):
        if isinstance(item, str):
            chunks.append(item)
        else:
            final = item

    assert "".join(chunks) == text
    assert final is not None
    assert final.text == text
