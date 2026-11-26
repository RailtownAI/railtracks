from unittest.mock import AsyncMock, Mock

import pytest
import railtracks as rt
from railtracks.llm import (
    MessageHistory,
    ToolMessage,
    ToolResponse,
    UserMessage,
)
from railtracks.prebuilt.middleware import ToolOutputSummarizer
from railtracks.prebuilt.middleware import tool_output_summarizer as module


async def test_rejects_node_middleware_slot(mock_llm):
    agent = rt.agent_node(
        "wrong-slot",
        llm=mock_llm(),
        middleware=[ToolOutputSummarizer(mock_llm())],
    )
    with pytest.raises(TypeError, match="_middleware_fn"):
        await rt.Flow("wrong-slot", agent).ainvoke("hello")


@pytest.fixture
def summary_call(monkeypatch):
    call = AsyncMock(return_value=Mock(content="Key finding."))
    monkeypatch.setattr(module, "call_node", call)
    return call


def _large_tool_message(result: str) -> ToolMessage:
    return ToolMessage(ToolResponse(identifier="call-1", name="search", result=result))


@pytest.mark.asyncio
async def test_summarizes_large_tool_output_and_preserves_tool_identity(
    mock_llm, summary_call
):
    summarizer = mock_llm()
    middleware = ToolOutputSummarizer(
        summarizer,
        max_chars=10,
        summary_max_chars=5,
        input_max_chars=100,
    )
    history = MessageHistory([UserMessage("Question"), _large_tool_message("x" * 11)])
    original_message = history[1]
    call = AsyncMock(return_value="model response")

    result = await middleware._middleware_fn(call, history, None, None)

    assert result == "model response"
    assert history[1] is original_message
    assert history[1].content.result == "x" * 11
    forwarded_history = call.await_args.args[0]
    assert forwarded_history is not history
    assert forwarded_history[0] is history[0]
    assert forwarded_history[1].content.identifier == "call-1"
    assert forwarded_history[1].content.name == "search"
    assert (
        forwarded_history[1].content.result
        == "[Summarized: original was 11 characters]\nKey f"
    )
    summary_call.assert_awaited_once()
    assert "at most 5 characters" in summary_call.await_args.args[1]
    call.assert_awaited_once_with(forwarded_history, None, None)


@pytest.mark.asyncio
async def test_leaves_small_and_non_tool_messages_unchanged(mock_llm, summary_call):
    summarizer = mock_llm()
    middleware = ToolOutputSummarizer(
        summarizer,
        max_chars=10,
        summary_max_chars=5,
    )
    small = _large_tool_message("short")
    user = UserMessage("x" * 20)
    history = MessageHistory([user, small])
    call = AsyncMock(return_value="model response")

    await middleware._middleware_fn(call, history, None, None)

    assert history[0] is user
    assert history[1] is small
    forwarded_history = call.await_args.args[0]
    assert forwarded_history is not history
    assert forwarded_history[0] is user
    assert forwarded_history[1] is small
    summary_call.assert_not_awaited()


@pytest.mark.asyncio
async def test_bounds_summarizer_input_and_keeps_original_when_it_fails(
    mock_llm, summary_call
):
    summarizer = mock_llm()
    summary_call.side_effect = RuntimeError("offline")
    middleware = ToolOutputSummarizer(
        summarizer,
        max_chars=10,
        summary_max_chars=5,
        input_max_chars=8,
    )
    original = _large_tool_message("0123456789ABCDEFGHIJ")
    history = MessageHistory([original])
    call = AsyncMock(return_value="model response")

    await middleware._middleware_fn(call, history, None, None)

    assert history[0] is original
    forwarded_history = call.await_args.args[0]
    assert forwarded_history is not history
    assert forwarded_history[0] is original
    assert "12 characters omitted" in summary_call.await_args.args[1]
    assert "0123" in summary_call.await_args.args[1]
    assert "GHIJ" in summary_call.await_args.args[1]
    call.assert_awaited_once_with(forwarded_history, None, None)


@pytest.mark.asyncio
async def test_duplicate_tool_ids_do_not_share_summaries(mock_llm, summary_call):
    summary_call.side_effect = [
        Mock(content="FIRST"),
        Mock(content="SECOND"),
        Mock(content="THIRD"),
    ]
    middleware = ToolOutputSummarizer(
        mock_llm(), max_chars=10, summary_max_chars=6, input_max_chars=100
    )
    large_first = ToolMessage(
        ToolResponse(identifier="same-id", name="search", result="a" * 11)
    )
    small_duplicate = ToolMessage(
        ToolResponse(identifier="same-id", name="search", result="short")
    )
    large_second = ToolMessage(
        ToolResponse(identifier="same-id", name="search", result="b" * 12)
    )
    same_result_other_tool = ToolMessage(
        ToolResponse(identifier="same-id", name="fetch", result="b" * 12)
    )
    history = MessageHistory(
        [large_first, small_duplicate, large_second, same_result_other_tool]
    )
    call = AsyncMock(return_value="model response")

    await middleware._middleware_fn(call, history, None, None)

    forwarded_history = call.await_args.args[0]
    assert history == [
        large_first,
        small_duplicate,
        large_second,
        same_result_other_tool,
    ]
    assert forwarded_history[0].content.result.endswith("\nFIRST")
    assert forwarded_history[1] is small_duplicate
    assert forwarded_history[2].content.result.endswith("\nSECOND")
    assert forwarded_history[3].content.result.endswith("\nTHIRD")
    assert summary_call.await_count == 3


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
