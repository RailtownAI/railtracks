"""Integration tests: agent_node + guardrails + mock LLM."""

from __future__ import annotations

import pytest
import railtracks as rt
from pydantic import BaseModel, Field

from railtracks.built_nodes.concrete import (
    GuardedStreamingStructuredLLM,
    GuardedStreamingTerminalLLM,
    GuardedStructuredLLM,
    GuardedTerminalLLM,
)
from railtracks.built_nodes.concrete.response import StringResponse, StructuredResponse
from railtracks.guardrails import Guard, GuardrailBlockedError, GuardrailDecision
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


@pytest.mark.asyncio
async def test_terminal_agent_uses_guarded_base_when_guardrails_set(
    mock_llm, allow_input
):
    llm = mock_llm()
    Agent = rt.agent_node(
        name="g-term",
        llm=llm,
        guardrails=Guard(input=[allow_input]),
    )
    assert issubclass(Agent, GuardedTerminalLLM)
    assert not issubclass(Agent, GuardedStreamingTerminalLLM)


@pytest.mark.asyncio
async def test_terminal_input_block_skips_llm(mock_llm, block_input):
    llm = mock_llm()
    counts = _counting_chat(llm)
    Agent = rt.agent_node(
        name="block-term",
        llm=llm,
        guardrails=Guard(input=[block_input]),
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
        guardrails=Guard(input=[allow_input]),
    )
    with rt.Session():
        out = await rt.call(Agent, user_input="hello")
    assert counts["n"] == 1
    assert isinstance(out, StringResponse)
    assert "ok" in out.text


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.asyncio
async def test_streaming_terminal_guardrails(mock_llm, allow_input, stream):
    llm = mock_llm(custom_response="streamed", stream=stream)
    counts = _counting_chat(llm)
    Agent = rt.agent_node(
        name="stream-term",
        llm=llm,
        guardrails=Guard(input=[allow_input]),
    )
    assert issubclass(Agent, GuardedStreamingTerminalLLM if stream else GuardedTerminalLLM)

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
        guardrails=Guard(input=[block_input]),
    )
    with rt.Session():
        with pytest.raises(GuardrailBlockedError):
            await rt.call(Agent, user_input="x")
    assert counts["n"] == 0


class _Answer(BaseModel):
    text: str = Field(default="ok")


@pytest.mark.asyncio
async def test_structured_agent_uses_guarded_base(mock_llm, allow_input):
    llm = mock_llm(custom_response='{"text":"from-llm"}')
    Agent = rt.agent_node(
        name="g-struct",
        output_schema=_Answer,
        llm=llm,
        guardrails=Guard(input=[allow_input]),
    )
    assert issubclass(Agent, GuardedStructuredLLM)


@pytest.mark.asyncio
async def test_structured_input_block_skips_llm(mock_llm, block_input):
    llm = mock_llm()
    counts = _counting_structured(llm)
    Agent = rt.agent_node(
        name="block-struct",
        output_schema=_Answer,
        llm=llm,
        guardrails=Guard(input=[block_input]),
    )
    with rt.Session():
        with pytest.raises(GuardrailBlockedError):
            await rt.call(Agent, user_input="q")
    assert counts["n"] == 0


@pytest.mark.asyncio
async def test_structured_output_block_after_llm(mock_llm, allow_input):
    llm = mock_llm(custom_response='{"text":"x"}')

    def block_out(_e) -> GuardrailDecision:  # type: ignore[no-untyped-def]
        return GuardrailDecision.block(reason="output policy")

    Agent = rt.agent_node(
        name="out-block",
        output_schema=_Answer,
        llm=llm,
        guardrails=Guard(input=[allow_input], output=[block_out]),
    )
    with rt.Session():
        with pytest.raises(GuardrailBlockedError):
            await rt.call(Agent, user_input="q")


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.asyncio
async def test_structured_streaming_guardrails(mock_llm, allow_input, stream):
    llm = mock_llm(custom_response='{"text":"s"}', stream=stream)
    counts = _counting_structured(llm)
    Agent = rt.agent_node(
        name="struct-stream",
        output_schema=_Answer,
        llm=llm,
        guardrails=Guard(input=[allow_input]),
    )
    assert issubclass(
        Agent,
        GuardedStreamingStructuredLLM if stream else GuardedStructuredLLM,
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


def test_tool_agent_guardrails_not_implemented(mock_llm):
    def tool_fn() -> int:
        return 1

    with pytest.raises(NotImplementedError, match="Guardrails"):
        rt.agent_node(
            name="tools",
            tool_nodes={rt.function_node(tool_fn)},
            llm=mock_llm(),
            guardrails=Guard(input=[lambda _e: GuardrailDecision.allow()]),
        )


def test_tool_structured_agent_guardrails_not_implemented(mock_llm):
    class M(BaseModel):
        v: int = 0

    def tool_fn() -> int:
        return 1

    with pytest.raises(NotImplementedError, match="Guardrails"):
        rt.agent_node(
            name="tools-s",
            tool_nodes={rt.function_node(tool_fn)},
            output_schema=M,
            llm=mock_llm(),
            guardrails=Guard(input=[lambda _e: GuardrailDecision.allow()]),
        )


@pytest.mark.asyncio
async def test_terminal_output_block(mock_llm, allow_input):
    llm = mock_llm(custom_response="bad-answer")

    def block_out(_e) -> GuardrailDecision:  # type: ignore[no-untyped-def]
        return GuardrailDecision.block(reason="no")

    Agent = rt.agent_node(
        name="term-out",
        llm=llm,
        guardrails=Guard(input=[allow_input], output=[block_out]),
    )
    with rt.Session():
        with pytest.raises(GuardrailBlockedError):
            await rt.call(Agent, user_input="q")
