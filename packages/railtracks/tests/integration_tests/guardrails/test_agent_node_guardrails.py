"""Integration tests: agent_node + guardrails + mock LLM."""

from __future__ import annotations

import pytest
import railtracks as rt
from pydantic import BaseModel, Field

from railtracks.built_nodes.llm.response import StringResponse, StructuredResponse
from railtracks.guardrails import GuardrailBlockedError, GuardrailDecision, InputGuard, LLMGuardrailEvent, OutputGuard
from railtracks.llm import AssistantMessage


class FnInputGuard(InputGuard):
    """Wrap a plain callable as an InputGuard for testing."""

    def __init__(self, fn, name: str | None = None):
        super().__init__(name=name)
        self._decision_fn = fn

    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision:
        return self._decision_fn(event)


class FnOutputGuard(OutputGuard):
    """Wrap a plain callable as an OutputGuard for testing."""

    def __init__(self, fn, name: str | None = None):
        super().__init__(name=name)
        self._decision_fn = fn

    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision:
        return self._decision_fn(event)
def _counting_chat(llm: rt.llm.ModelBase):
    state = {"n": 0}
    real = llm._chat

    def wrapped(messages, **kwargs):  # type: ignore[no-untyped-def]
        state["n"] += 1
        return real(messages, **kwargs)

    llm._chat = wrapped  # type: ignore[method-assign]
    return state


def _counting_structured(llm: rt.llm.ModelBase):
    state = {"n": 0}
    real = llm._structured

    def wrapped(messages, schema, **kwargs):  # type: ignore[no-untyped-def]
        state["n"] += 1
        return real(messages, schema, **kwargs)

    llm._structured = wrapped  # type: ignore[method-assign]
    return state


def _counting_chat_with_tools(llm: rt.llm.ModelBase):
    state = {"n": 0}
    real = llm._chat_with_tools

    def wrapped(messages, tools, **kwargs):  # type: ignore[no-untyped-def]
        state["n"] += 1
        return real(messages, tools, **kwargs)

    llm._chat_with_tools = wrapped  # type: ignore[method-assign]
    return state


@pytest.mark.asyncio
async def test_terminal_input_block_skips_llm(mock_llm, block_input):
    llm = mock_llm()
    counts = _counting_chat(llm)
    Agent = rt.agent_node(
        name="block-term",
        llm=llm,
        model_middleware=[block_input],
    )
    with rt.Session():
        with pytest.raises(GuardrailBlockedError):
            await rt.call(Agent, user_input="hello")
    assert counts["n"] == 0


@pytest.mark.asyncio
async def test_terminal_input_allow_calls_llm(mock_llm, allow_input):
    llm = mock_llm(custom_response="ok")
    counts = _counting_chat(llm)
    Agent = rt.agent_node(
        name="allow-term",
        llm=llm,
        model_middleware=[allow_input],
    )
    with rt.Session():
        out = await rt.call(Agent, user_input="hello")
    assert counts["n"] == 1
    assert isinstance(out, StringResponse)
    assert "ok" in out.text


@pytest.mark.parametrize(
    "stream",
    [
        False,
        pytest.param(
            True,
            marks=pytest.mark.xfail(
                reason=(
                    "Pre-existing, guardrail-unrelated bug: model_invoker._llm_observe "
                    "always does `response.message`, but ModelBase.chat() returns a raw "
                    "generator when stream=True. Reproduces with zero guardrails involved."
                ),
                strict=True,
            ),
        ),
    ],
)
@pytest.mark.asyncio
async def test_streaming_terminal_guardrails(mock_llm, allow_input, stream):
    llm = mock_llm(custom_response="streamed", stream=stream)
    counts = _counting_chat(llm)
    Agent = rt.agent_node(
        name="stream-term",
        llm=llm,
        model_middleware=[allow_input],
    )

    with rt.Session():
        result = await rt.call(Agent, user_input="hi")

    assert counts["n"] == 1
    if stream:
        collected: StringResponse | None = None
        for chunk in result:
            if isinstance(chunk, StringResponse):
                collected = chunk
        assert collected is not None
        assert "streamed" in collected.text
    else:
        assert isinstance(result, StringResponse)
        assert "streamed" in result.text


@pytest.mark.asyncio
async def test_streaming_terminal_input_block_skips_llm(mock_llm, block_input):
    llm = mock_llm(stream=True)
    counts = _counting_chat(llm)
    Agent = rt.agent_node(
        name="block-stream",
        llm=llm,
        model_middleware=[block_input],
    )
    with rt.Session():
        with pytest.raises(GuardrailBlockedError):
            await rt.call(Agent, user_input="x")
    assert counts["n"] == 0


class _Answer(BaseModel):
    text: str = Field(default="ok")


@pytest.mark.asyncio
async def test_structured_input_block_skips_llm(mock_llm, block_input):
    llm = mock_llm()
    counts = _counting_structured(llm)
    Agent = rt.agent_node(
        name="block-struct",
        output_schema=_Answer,
        llm=llm,
        model_middleware=[block_input],
    )
    with rt.Session():
        with pytest.raises(GuardrailBlockedError):
            await rt.call(Agent, user_input="q")
    assert counts["n"] == 0


@pytest.mark.asyncio
async def test_structured_output_block_after_llm(mock_llm, allow_input):
    llm = mock_llm(custom_response='{"text":"x"}')

    Agent = rt.agent_node(
        name="out-block",
        output_schema=_Answer,
        llm=llm,
        model_middleware=[
            allow_input,
            FnOutputGuard(lambda _e: GuardrailDecision.block(reason="output policy")),
        ],
    )
    with rt.Session():
        with pytest.raises(GuardrailBlockedError):
            await rt.call(Agent, user_input="q")


@pytest.mark.parametrize(
    "stream",
    [
        False,
        pytest.param(
            True,
            marks=pytest.mark.xfail(
                reason=(
                    "Pre-existing, guardrail-unrelated bug: model_invoker._llm_observe "
                    "always does `response.message`, but ModelBase.chat() returns a raw "
                    "generator when stream=True. Reproduces with zero guardrails involved."
                ),
                strict=True,
            ),
        ),
    ],
)
@pytest.mark.asyncio
async def test_structured_streaming_guardrails(mock_llm, allow_input, stream):
    llm = mock_llm(custom_response='{"text":"s"}', stream=stream)
    counts = _counting_structured(llm)
    Agent = rt.agent_node(
        name="struct-stream",
        output_schema=_Answer,
        llm=llm,
        model_middleware=[allow_input],
    )

    with rt.Session():
        result = await rt.call(Agent, user_input="hi")

    assert counts["n"] == 1
    if stream:
        final: StructuredResponse[_Answer] | None = None
        for chunk in result:
            if isinstance(chunk, StructuredResponse):
                final = chunk
        assert final is not None
        assert final.structured.text == "s"
    else:
        assert isinstance(result, StructuredResponse)
        assert result.structured.text == "s"




@pytest.mark.asyncio
async def test_terminal_output_block(mock_llm, allow_input):
    llm = mock_llm(custom_response="bad-answer")

    Agent = rt.agent_node(
        name="term-out",
        llm=llm,
        model_middleware=[
            allow_input,
            FnOutputGuard(lambda _e: GuardrailDecision.block(reason="no")),
        ],
    )
    with rt.Session():
        with pytest.raises(GuardrailBlockedError):
            await rt.call(Agent, user_input="q")


# ============================================================
# ToolCallLLM guardrail tests
# ============================================================


@pytest.mark.asyncio
async def test_tool_call_input_block_skips_llm(mock_llm, block_input):
    def tool_fn() -> str:
        return "result"

    llm = mock_llm()
    counts = _counting_chat_with_tools(llm)
    Agent = rt.agent_node(
        name="block-tool",
        tool_nodes={rt.function_node(tool_fn)},
        llm=llm,
        model_middleware=[block_input],
    )
    with rt.Session():
        with pytest.raises(GuardrailBlockedError):
            await rt.call(Agent, user_input="hello")
    assert counts["n"] == 0


@pytest.mark.asyncio
async def test_tool_call_input_allow_calls_llm(mock_llm, allow_input):
    def tool_fn() -> str:
        return "result"

    llm = mock_llm()
    counts = _counting_chat_with_tools(llm)
    Agent = rt.agent_node(
        name="allow-tool",
        tool_nodes={rt.function_node(tool_fn)},
        llm=llm,
        model_middleware=[allow_input],
    )
    with rt.Session():
        out = await rt.call(Agent, user_input="hello")
    assert counts["n"] >= 1
    assert isinstance(out, StringResponse)


@pytest.mark.asyncio
async def test_tool_call_output_block(mock_llm, allow_input):
    def tool_fn() -> str:
        return "result"

    Agent = rt.agent_node(
        name="out-block-tool",
        tool_nodes={rt.function_node(tool_fn)},
        llm=mock_llm(),
        model_middleware=[
            allow_input,
            FnOutputGuard(lambda _e: GuardrailDecision.block(reason="blocked output")),
        ],
    )
    with rt.Session():
        with pytest.raises(GuardrailBlockedError):
            await rt.call(Agent, user_input="hello")


@pytest.mark.asyncio
async def test_tool_call_output_transform_updates_response_and_history(mock_llm, allow_input):
    """TRANSFORM: resp.content and resp.message_history[-1].content must both reflect the new message."""
    TRANSFORMED = "transformed content"

    def tool_fn() -> str:
        return "result"

    Agent = rt.agent_node(
        name="out-transform-tool",
        tool_nodes={rt.function_node(tool_fn)},
        llm=mock_llm(),
        model_middleware=[
            allow_input,
            FnOutputGuard(lambda _e: GuardrailDecision.transform_output(
                output_message=AssistantMessage(TRANSFORMED),
                reason="transform applied",
            )),
        ],
    )
    with rt.Session():
        result = await rt.call(Agent, user_input="hello")
    assert isinstance(result, StringResponse)
    assert result.content == TRANSFORMED
    assert result.message_history[-1].content == TRANSFORMED


@pytest.mark.asyncio
async def test_tool_call_output_guard_fires_per_model_round_trip(mock_llm, allow_input):
    """OutputGuard is plain model_middleware: it wraps every raw model call inside the
    tool-calling loop (once for the tool-call turn, once for the final reply), not just
    the final reply. The old Guarded*LLM hierarchy special-cased "final reply only"; that
    guarantee no longer holds now that guards are ordinary model_middleware entries.
    """
    @rt.function_node
    async def weather_tool(city: str) -> str:
        """Get weather for a city.
        Args:
            city (str)
        """
        return f"Sunny in {city}"

    fire_count = {"n": 0}

    def _counting_guard(event: LLMGuardrailEvent) -> GuardrailDecision:
        fire_count["n"] += 1
        return GuardrailDecision.allow()

    llm = mock_llm(
        requested_tool_calls=[
            rt.llm.ToolCall(name="weather_tool", identifier="tc_1", arguments={"city": "NYC"})
        ]
    )
    Agent = rt.agent_node(
        name="fires-once",
        tool_nodes={weather_tool},
        llm=llm,
        model_middleware=[allow_input, FnOutputGuard(_counting_guard)],
    )
    with rt.Session():
        await rt.call(Agent, user_input="weather?")

    assert fire_count["n"] == 2


# ============================================================
# StreamingToolCallLLM guardrail tests
# ============================================================


@pytest.mark.asyncio
async def test_streaming_tool_call_input_block(mock_llm, block_input):
    def tool_fn() -> str:
        return "result"

    llm = mock_llm(stream=True)
    counts = _counting_chat_with_tools(llm)
    Agent = rt.agent_node(
        name="block-stream-tool",
        tool_nodes={rt.function_node(tool_fn)},
        llm=llm,
        model_middleware=[block_input],
    )
    with rt.Session():
        with pytest.raises(GuardrailBlockedError):
            await rt.call(Agent, user_input="hello")
    assert counts["n"] == 0


# ============================================================
# StructuredToolCallLLM guardrail tests
# ============================================================


@pytest.mark.asyncio
async def test_structured_tool_call_input_block_skips_llm(mock_llm, block_input):
    def tool_fn() -> str:
        return "result"

    llm = mock_llm()
    counts = _counting_chat_with_tools(llm)
    Agent = rt.agent_node(
        name="block-struct-tool",
        tool_nodes={rt.function_node(tool_fn)},
        output_schema=_Answer,
        llm=llm,
        model_middleware=[block_input],
    )
    with rt.Session():
        with pytest.raises(GuardrailBlockedError):
            await rt.call(Agent, user_input="q")
    assert counts["n"] == 0
