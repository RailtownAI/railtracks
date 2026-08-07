"""Unit tests for ModelInvoker — the shared choke point for the middleware chain
(guardrails/prebuilt middleware run through it) and for streaming (the
`_stream_queue_if_enabled` / `_drain_to_queue` decision logic lives here).
"""

from __future__ import annotations

import asyncio

import pytest
from railtracks.built_nodes.llm import model_invoker as model_invoker_module
from railtracks.built_nodes.llm.middleware import wrap_llm
from railtracks.built_nodes.llm.model_invoker import (
    ModelInvoker,
    _drain_to_queue,
    _llm_observe,
    _stream_queue_if_enabled,
)
from railtracks.exceptions.errors import LLMError
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import AssistantMessage, UserMessage
from railtracks.llm.providers import ModelProvider
from railtracks.llm.response import MessageInfo, Response
from railtracks.llm.tools.tool import Tool


def _make_response(text: str = "hi") -> Response:
    return Response(
        message=AssistantMessage(content=text),
        message_info=MessageInfo(
            input_tokens=1,
            output_tokens=2,
            latency=0.1,
            model_name="stub-model",
            total_cost=0.0,
            system_fingerprint="fp",
        ),
    )


def _make_tool() -> Tool:
    return Tool(name="a_tool", detail="does a thing", parameters=[])


class _StubModel:
    """Minimal ModelBase-shaped stub recording every buffered/streaming call made on it."""

    def __init__(
        self,
        provider: ModelProvider = ModelProvider.OPENAI,
        response: Response | None = None,
        stream_items: list | None = None,
        raise_on_chat: Exception | None = None,
    ):
        self._provider = provider
        self._response = response or _make_response()
        self._stream_items = stream_items if stream_items is not None else [self._response]
        self._raise_on_chat = raise_on_chat
        self.calls: list[tuple] = []

    def model_provider(self):
        return self._provider

    # --- buffered ---
    def chat(self, messages):
        self.calls.append(("chat", messages))
        if self._raise_on_chat is not None:
            raise self._raise_on_chat
        return self._response

    def chat_with_tools(self, messages, tools):
        self.calls.append(("chat_with_tools", messages, tools))
        return self._response

    def structured(self, messages, schema):
        self.calls.append(("structured", messages, schema))
        return self._response

    # --- streaming ---
    async def astream_chat(self, messages):
        self.calls.append(("astream_chat", messages))
        for item in self._stream_items:
            yield item

    async def astream_chat_with_tools(self, messages, tools):
        self.calls.append(("astream_chat_with_tools", messages, tools))
        for item in self._stream_items:
            yield item

    async def astream_structured(self, messages, schema):
        self.calls.append(("astream_structured", messages, schema))
        for item in self._stream_items:
            yield item


@pytest.fixture
def messages() -> MessageHistory:
    return MessageHistory([UserMessage("hello")])


# ---------------------------------------------------------------------------
# _stream_queue_if_enabled
# ---------------------------------------------------------------------------


def test_stream_queue_if_enabled_returns_none_when_no_queue_set(monkeypatch):
    monkeypatch.setattr(model_invoker_module, "get_stream_queue", lambda: None)
    model = _StubModel()

    assert _stream_queue_if_enabled(model, None) is None
    assert _stream_queue_if_enabled(model, [_make_tool()]) is None


def test_stream_queue_if_enabled_returns_queue_when_no_tools(monkeypatch):
    queue: asyncio.Queue = asyncio.Queue()
    monkeypatch.setattr(model_invoker_module, "get_stream_queue", lambda: queue)
    model = _StubModel(provider=ModelProvider.OPENAI)

    assert _stream_queue_if_enabled(model, None) is queue
    assert _stream_queue_if_enabled(model, []) is queue


def test_stream_queue_if_enabled_returns_queue_for_non_blacklisted_provider_with_tools(
    monkeypatch,
):
    queue: asyncio.Queue = asyncio.Queue()
    monkeypatch.setattr(model_invoker_module, "get_stream_queue", lambda: queue)
    model = _StubModel(provider=ModelProvider.OPENAI)

    assert _stream_queue_if_enabled(model, [_make_tool()]) is queue


def test_stream_queue_if_enabled_falls_back_for_blacklisted_provider_with_tools(
    monkeypatch, caplog
):
    queue: asyncio.Queue = asyncio.Queue()
    monkeypatch.setattr(model_invoker_module, "get_stream_queue", lambda: queue)
    model = _StubModel(provider=ModelProvider.ANTHROPIC)

    with caplog.at_level("WARNING"):
        result = _stream_queue_if_enabled(model, [_make_tool()])

    assert result is None
    assert any(
        "falling back to a" in record.message for record in caplog.records
    )


# ---------------------------------------------------------------------------
# _drain_to_queue
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_drain_to_queue_forwards_chunks_in_order_and_returns_response():
    response = _make_response("abc")

    async def model_stream():
        yield "a"
        yield "b"
        yield "c"
        yield response

    queue: asyncio.Queue = asyncio.Queue()
    result = await _drain_to_queue(model_stream(), queue)

    assert result is response
    forwarded = [queue.get_nowait() for _ in range(3)]
    assert forwarded == [("chunk", "a"), ("chunk", "b"), ("chunk", "c")]
    assert queue.empty()


@pytest.mark.asyncio
async def test_drain_to_queue_raises_llmerror_when_stream_never_yields_a_response():
    async def model_stream():
        yield "a"
        yield "b"

    queue: asyncio.Queue = asyncio.Queue()
    with pytest.raises(LLMError):
        await _drain_to_queue(model_stream(), queue)


# ---------------------------------------------------------------------------
# ModelInvoker.invoke — buffered dispatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invoke_buffered_plain_chat_dispatch(monkeypatch, messages):
    monkeypatch.setattr(model_invoker_module, "get_stream_queue", lambda: None)
    model = _StubModel()
    invoker = ModelInvoker(model)

    result = await invoker.invoke(messages)

    assert result is model._response
    assert model.calls == [("chat", messages)]


@pytest.mark.asyncio
async def test_invoke_buffered_chat_with_tools_dispatch(monkeypatch, messages):
    monkeypatch.setattr(model_invoker_module, "get_stream_queue", lambda: None)
    tool = _make_tool()
    model = _StubModel()
    invoker = ModelInvoker(model)

    result = await invoker.invoke(messages, tools=[tool])

    assert result is model._response
    assert model.calls == [("chat_with_tools", messages, [tool])]


@pytest.mark.asyncio
async def test_invoke_buffered_structured_dispatch(monkeypatch, messages):
    monkeypatch.setattr(model_invoker_module, "get_stream_queue", lambda: None)
    from pydantic import BaseModel

    class Schema(BaseModel):
        x: int = 1

    model = _StubModel()
    invoker = ModelInvoker(model)

    result = await invoker.invoke(messages, schema=Schema)

    assert result is model._response
    assert model.calls == [("structured", messages, Schema)]


@pytest.mark.asyncio
async def test_invoke_buffered_tools_take_priority_over_schema(monkeypatch, messages):
    monkeypatch.setattr(model_invoker_module, "get_stream_queue", lambda: None)
    from pydantic import BaseModel

    class Schema(BaseModel):
        x: int = 1

    tool = _make_tool()
    model = _StubModel()
    invoker = ModelInvoker(model)

    await invoker.invoke(messages, schema=Schema, tools=[tool])

    assert model.calls == [("chat_with_tools", messages, [tool])]


# ---------------------------------------------------------------------------
# ModelInvoker.invoke — streaming dispatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invoke_streaming_plain_chat_dispatch(monkeypatch, messages):
    queue: asyncio.Queue = asyncio.Queue()
    monkeypatch.setattr(model_invoker_module, "get_stream_queue", lambda: queue)
    response = _make_response("hi")
    model = _StubModel(stream_items=["h", "i", response])
    invoker = ModelInvoker(model)

    result = await invoker.invoke(messages)

    assert result is response
    assert model.calls == [("astream_chat", messages)]
    assert queue.get_nowait() == ("chunk", "h")
    assert queue.get_nowait() == ("chunk", "i")
    assert queue.empty()


@pytest.mark.asyncio
async def test_invoke_streaming_chat_with_tools_dispatch(monkeypatch, messages):
    queue: asyncio.Queue = asyncio.Queue()
    monkeypatch.setattr(model_invoker_module, "get_stream_queue", lambda: queue)
    tool = _make_tool()
    response = _make_response("hi")
    model = _StubModel(provider=ModelProvider.OPENAI, stream_items=[response])
    invoker = ModelInvoker(model)

    result = await invoker.invoke(messages, tools=[tool])

    assert result is response
    assert model.calls == [("astream_chat_with_tools", messages, [tool])]


@pytest.mark.asyncio
async def test_invoke_streaming_structured_dispatch(monkeypatch, messages):
    queue: asyncio.Queue = asyncio.Queue()
    monkeypatch.setattr(model_invoker_module, "get_stream_queue", lambda: queue)
    from pydantic import BaseModel

    class Schema(BaseModel):
        x: int = 1

    response = _make_response("hi")
    model = _StubModel(stream_items=[response])
    invoker = ModelInvoker(model)

    result = await invoker.invoke(messages, schema=Schema)

    assert result is response
    assert model.calls == [("astream_structured", messages, Schema)]


@pytest.mark.asyncio
async def test_invoke_streaming_falls_back_to_buffered_for_blacklisted_provider_with_tools(
    monkeypatch, messages
):
    queue: asyncio.Queue = asyncio.Queue()
    monkeypatch.setattr(model_invoker_module, "get_stream_queue", lambda: queue)
    tool = _make_tool()
    model = _StubModel(provider=ModelProvider.ANTHROPIC)
    invoker = ModelInvoker(model)

    result = await invoker.invoke(messages, tools=[tool])

    assert result is model._response
    # buffered chat_with_tools was used, not the streaming variant
    assert model.calls == [("chat_with_tools", messages, [tool])]
    # nothing was pushed onto the (unused) stream queue
    assert queue.empty()


# ---------------------------------------------------------------------------
# create_with_llm_observe
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_with_llm_observe_appends_observe_as_the_innermost_middleware(
    monkeypatch, messages
):
    monkeypatch.setattr(model_invoker_module, "get_stream_queue", lambda: None)

    @wrap_llm
    async def tracer(call, message_history, schema, tools):
        return await call(message_history, schema, tools)

    invoker = ModelInvoker.create_with_llm_observe(_StubModel(), [tracer])

    chain = invoker._middleware.middleware
    assert len(chain) == 2
    # user middleware is deep-copied (see below), but the shape/name is preserved
    assert chain[0].name == tracer.name
    # the built-in observation middleware itself is not copied — same singleton instance
    assert chain[1] is _llm_observe


def test_create_with_llm_observe_deep_copies_caller_middleware_list(monkeypatch):
    @wrap_llm
    async def tracer(call, message_history, schema, tools):
        return await call(message_history, schema, tools)

    middleware_list = [tracer]
    invoker = ModelInvoker.create_with_llm_observe(_StubModel(), middleware_list)

    # a fresh (deep-copied) middleware object was stored, not the caller's original
    chain = invoker._middleware.middleware
    assert chain[0] is not tracer
    assert chain[0].name == tracer.name

    # mutating the caller's list after construction must not leak into the invoker
    middleware_list.append(tracer)
    middleware_list.clear()

    chain = invoker._middleware.middleware
    assert len(chain) == 2
    assert chain[1] is _llm_observe


@pytest.mark.asyncio
async def test_create_with_llm_observe_default_middleware_is_just_observe(monkeypatch, messages):
    monkeypatch.setattr(model_invoker_module, "get_stream_queue", lambda: None)
    invoker = ModelInvoker.create_with_llm_observe(_StubModel())

    chain = invoker._middleware.middleware
    assert chain == [_llm_observe]

    result = await invoker.invoke(messages)
    assert result is not None


@pytest.mark.asyncio
async def test_llm_observe_propagates_exceptions_from_the_core_call(monkeypatch, messages):
    monkeypatch.setattr(model_invoker_module, "get_stream_queue", lambda: None)
    model = _StubModel(raise_on_chat=ValueError("boom"))
    invoker = ModelInvoker.create_with_llm_observe(model)

    with pytest.raises(ValueError, match="boom"):
        await invoker.invoke(messages)


# ---------------------------------------------------------------------------
# Regression guard: the dead `extend_middleware` instance method was removed
# ---------------------------------------------------------------------------


def test_model_invoker_has_no_extend_middleware_method():
    assert not hasattr(ModelInvoker, "extend_middleware")
