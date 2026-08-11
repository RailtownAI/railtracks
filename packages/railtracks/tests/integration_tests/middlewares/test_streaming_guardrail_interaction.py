"""Integration tests for rt.astream + guardrails/model_middleware interaction.

`OutputGuard._middleware_fn` awaits the *entire* raw model call (including the
streaming drain-to-queue path) before inspecting/transforming/blocking the
response -- meaning any chunks already pushed onto the astream queue cannot be
un-sent. These tests pin down what that means in practice: TRANSFORM can make
the streamed chunks diverge from `.result`, and BLOCK still propagates cleanly
even though chunks may have already been delivered. Zero tests combined
streaming with guardrails/model_middleware before this file.
"""

from __future__ import annotations

import pytest
import railtracks as rt
from railtracks.built_nodes.llm.middleware import before_llm
from railtracks.guardrails.core import (
    GuardrailBlockedError,
    GuardrailDecision,
    InputGuard,
    LLMGuardrailEvent,
    OutputGuard,
)


class FnInputGuard(InputGuard):
    def __init__(self, fn, name: str | None = None):
        super().__init__(name=name)
        self._decision_fn = fn

    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision:
        return self._decision_fn(event)


class FnOutputGuard(OutputGuard):
    def __init__(self, fn, name: str | None = None):
        super().__init__(name=name)
        self._decision_fn = fn

    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision:
        return self._decision_fn(event)


def _agent(mock_llm, response, model_middleware):
    return rt.agent_node(
        name="StreamingGuardedAgent",
        system_message="stream",
        llm=mock_llm(response),
        model_middleware=model_middleware,
    )


@pytest.mark.asyncio
async def test_output_guard_block_propagates_out_of_stream(mock_llm):
    """A BLOCKing output guard's error propagates out of the stream, exactly like
    rt.call, even though the raw response was already fully generated/queued."""
    block = FnOutputGuard(lambda _e: GuardrailDecision.block(reason="nope"))
    agent = _agent(mock_llm, "Echo", [block])

    stream = rt.astream(agent, user_input="go")
    with pytest.raises(GuardrailBlockedError):
        async for _ in stream:
            pass

    # the stream is left in a finished/errored state; re-accessing it re-raises
    # cleanly rather than hanging or misbehaving.
    with pytest.raises(GuardrailBlockedError):
        await stream


@pytest.mark.asyncio
async def test_input_guard_block_emits_no_chunks(mock_llm):
    """An InputGuard blocks before the model is ever called, so no chunks are
    queued at all -- unlike an OutputGuard block, which happens after the chunks
    already streamed."""
    block = FnInputGuard(lambda _e: GuardrailDecision.block(reason="nope"))
    agent = _agent(mock_llm, "Echo", [block])

    stream = rt.astream(agent, user_input="go")
    chunks = []
    with pytest.raises(GuardrailBlockedError):
        async for chunk in stream:
            chunks.append(chunk)

    assert chunks == []


@pytest.mark.asyncio
async def test_output_guard_transform_diverges_from_streamed_chunks(mock_llm):
    """The output guard only sees the response after the whole (already-streamed)
    call completes, so a TRANSFORM changes `.result` without un-sending chunks --
    the streamed text and the final result legitimately differ."""

    def replace_with_redacted(event: LLMGuardrailEvent) -> GuardrailDecision:
        return GuardrailDecision.transform_output(
            output_message=event.output_message.__class__(content="[REDACTED]"),
            reason="redact",
        )

    transform = FnOutputGuard(replace_with_redacted)
    agent = _agent(mock_llm, "Echo", [transform])

    stream = rt.astream(agent, user_input="go")
    chunks = [chunk async for chunk in stream]

    # the raw model output was already streamed char-by-char before the guard ran
    assert "".join(chunks) == "Echo"
    # but the guard's transform is what `.result` actually reflects
    assert stream.result.text == "[REDACTED]"
    assert "".join(chunks) != stream.result.text


@pytest.mark.asyncio
async def test_output_guard_and_plain_middleware_both_fire_while_streaming(mock_llm):
    """A guard and a plain (non-guard) model_middleware both run around a streamed
    call. `before_llm` only hooks the "in" side and `OutputGuard` only hooks the
    "out" side, so (unlike two same-side entries) their relative order is fixed
    regardless of list position: the before-hook always completes before the
    after-hook runs, no matter which nests inside the other."""
    trace = []

    @before_llm
    async def plain_tracer(message_history, schema, tools):
        trace.append("plain")
        return message_history, schema, tools

    guard = FnOutputGuard(
        lambda _e: (trace.append("guard"), GuardrailDecision.allow())[1]
    )

    for model_middleware in ([plain_tracer, guard], [guard, plain_tracer]):
        trace.clear()
        agent = _agent(mock_llm, "Echo", model_middleware)

        stream = rt.astream(agent, user_input="go")
        chunks = [chunk async for chunk in stream]

        assert "".join(chunks) == "Echo"
        assert stream.result.text == "Echo"
        assert trace == ["plain", "guard"]
