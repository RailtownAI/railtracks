"""Unit tests for InputGuard/OutputGuard as ModelMiddleware: `_middleware_fn` /
`_input_wrapper` / `_output_wrapper`. These are exercised elsewhere only indirectly
through full agent_node integration tests; here each guard is wired directly via
`.wrap(fake_call)` and awaited, with no node/model involved.
"""

from __future__ import annotations

import pytest
from railtracks.guardrails.core import (
    GuardrailBlockedError,
    GuardrailDecision,
    InputGuard,
    LLMGuardrailEvent,
    OutputGuard,
)
from railtracks.llm import AssistantMessage, MessageHistory, ToolCall, UserMessage
from railtracks.llm.response import MessageInfo, Response


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


def _make_response(text: str = "hi") -> Response:
    return Response(message=AssistantMessage(text), message_info=MessageInfo(model_name="m"))


# ---------------------------------------------------------------------------
# InputGuard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_input_guard_allow_passes_history_through_unchanged():
    seen = {}

    async def fake_call(message_history, schema, tools):
        seen["message_history"] = message_history
        seen["schema"] = schema
        seen["tools"] = tools
        return _make_response("ok")

    guard = FnInputGuard(lambda _e: GuardrailDecision.allow())
    original = MessageHistory([UserMessage("hi")])

    result = await guard.wrap(fake_call)(original, None, None)

    assert seen["message_history"] == original
    assert result.message.content == "ok"


@pytest.mark.asyncio
async def test_input_guard_transform_rewrites_history_before_call():
    seen = {}
    new_history = MessageHistory([UserMessage("redacted")])

    async def fake_call(message_history, schema, tools):
        seen["message_history"] = message_history
        return _make_response("ok")

    guard = FnInputGuard(
        lambda _e: GuardrailDecision.transform_messages(messages=new_history, reason="t")
    )
    original = MessageHistory([UserMessage("hi, my email is a@b.com")])

    await guard.wrap(fake_call)(original, None, None)

    assert seen["message_history"] == new_history
    assert seen["message_history"] != original


@pytest.mark.asyncio
async def test_input_guard_block_raises_and_never_calls_onward():
    call_count = {"n": 0}

    async def fake_call(message_history, schema, tools):
        call_count["n"] += 1
        return _make_response("should not happen")

    guard = FnInputGuard(
        lambda _e: GuardrailDecision.block(reason="nope", user_facing_message="blocked")
    )

    with pytest.raises(GuardrailBlockedError) as exc:
        await guard.wrap(fake_call)(MessageHistory([UserMessage("hi")]), None, None)

    assert call_count["n"] == 0
    assert exc.value.reason == "nope"
    assert exc.value.user_facing_message == "blocked"


# ---------------------------------------------------------------------------
# OutputGuard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_output_guard_allow_returns_the_same_response_object():
    response = _make_response("hi")

    async def fake_call(message_history, schema, tools):
        return response

    guard = FnOutputGuard(lambda _e: GuardrailDecision.allow())
    result = await guard.wrap(fake_call)(MessageHistory([UserMessage("q")]), None, None)

    assert result is response  # identity: allow must not rebuild the Response


@pytest.mark.asyncio
async def test_output_guard_transform_rebuilds_response_preserving_message_info():
    original = _make_response("raw")
    new_message = AssistantMessage("sanitized")

    async def fake_call(message_history, schema, tools):
        return original

    guard = FnOutputGuard(
        lambda _e: GuardrailDecision.transform_output(output_message=new_message, reason="fix")
    )
    result = await guard.wrap(fake_call)(MessageHistory([UserMessage("q")]), None, None)

    assert result is not original
    assert result.message == new_message
    assert result.message_info is original.message_info


@pytest.mark.asyncio
async def test_output_guard_block_raises_after_call_was_made():
    call_count = {"n": 0}

    async def fake_call(message_history, schema, tools):
        call_count["n"] += 1
        return _make_response("leaked secret")

    guard = FnOutputGuard(lambda _e: GuardrailDecision.block(reason="leak"))

    with pytest.raises(GuardrailBlockedError):
        await guard.wrap(fake_call)(MessageHistory([UserMessage("q")]), None, None)

    assert call_count["n"] == 1  # unlike InputGuard, the model call already happened


@pytest.mark.asyncio
async def test_output_guard_skips_intermediate_tool_call_turns():
    tool_call_response = Response(
        message=AssistantMessage(
            [ToolCall(name="search", identifier="tc_1", arguments={})]
        ),
        message_info=MessageInfo(model_name="m"),
    )

    async def fake_call(message_history, schema, tools):
        return tool_call_response

    guard_fired = {"n": 0}

    def _guard(_e):
        guard_fired["n"] += 1
        return GuardrailDecision.block(reason="would break the tool loop")

    guard = FnOutputGuard(_guard)
    result = await guard.wrap(fake_call)(MessageHistory([UserMessage("q")]), None, None)

    assert guard_fired["n"] == 0  # tool-requesting turns are intermediate: never guarded
    assert result is tool_call_response  # passed through untouched, tool calls intact
