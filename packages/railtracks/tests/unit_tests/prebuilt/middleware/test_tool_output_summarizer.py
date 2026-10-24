from unittest.mock import AsyncMock

import pytest
from railtracks.llm import (
    AssistantMessage,
    MessageHistory,
    Response,
    ToolMessage,
    ToolResponse,
    UserMessage,
)
from railtracks.prebuilt.middleware import ToolOutputSummarizer


def _large_tool_message(result: str) -> ToolMessage:
    return ToolMessage(ToolResponse(identifier="call-1", name="search", result=result))


@pytest.mark.asyncio
async def test_summarizes_large_tool_output_and_preserves_tool_identity():
    summarizer = AsyncMock()
    summarizer.achat.return_value = Response(AssistantMessage("Key finding."))
    middleware = ToolOutputSummarizer(
        summarizer,
        max_chars=10,
        summary_max_chars=5,
        input_max_chars=100,
    )
    history = MessageHistory([UserMessage("Question"), _large_tool_message("x" * 11)])
    call = AsyncMock(return_value="model response")

    result = await middleware._middleware_fn(call, history)

    assert result == "model response"
    assert history[1].content.identifier == "call-1"
    assert history[1].content.name == "search"
    assert history[1].content.result == "Key f"
    summarizer.achat.assert_awaited_once()
    call.assert_awaited_once_with(history)


@pytest.mark.asyncio
async def test_leaves_small_and_non_tool_messages_unchanged():
    summarizer = AsyncMock()
    middleware = ToolOutputSummarizer(
        summarizer,
        max_chars=10,
        summary_max_chars=5,
    )
    small = _large_tool_message("short")
    user = UserMessage("x" * 20)
    history = MessageHistory([user, small])
    call = AsyncMock(return_value="model response")

    await middleware._middleware_fn(call, history)

    assert history[0] is user
    assert history[1] is small
    summarizer.achat.assert_not_awaited()


@pytest.mark.asyncio
async def test_bounds_summarizer_input_and_keeps_original_when_it_fails():
    summarizer = AsyncMock()
    summarizer.achat.side_effect = RuntimeError("offline")
    middleware = ToolOutputSummarizer(
        summarizer,
        max_chars=10,
        summary_max_chars=5,
        input_max_chars=8,
    )
    original = _large_tool_message("0123456789ABCDEFGHIJ")
    history = MessageHistory([original])
    call = AsyncMock(return_value="model response")

    await middleware._middleware_fn(call, history)

    assert history[0] is original
    assert "12 characters omitted" in summarizer.achat.await_args.args[0][1].content
    call.assert_awaited_once_with(history)


@pytest.mark.parametrize(
    ("max_chars", "summary_max_chars", "input_max_chars"),
    [(0, 1, 2), (2, 2, 3), (2, 0, 3), (2, 1, 0)],
)
def test_rejects_invalid_character_limits(
    max_chars, summary_max_chars, input_max_chars
):
    with pytest.raises(ValueError):
        ToolOutputSummarizer(
            AsyncMock(),
            max_chars=max_chars,
            summary_max_chars=summary_max_chars,
            input_max_chars=input_max_chars,
        )
