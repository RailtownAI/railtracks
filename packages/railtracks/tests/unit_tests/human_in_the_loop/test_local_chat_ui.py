"""Regression tests for tool-failure state reported by the local chat UI."""

import asyncio

from railtracks.human_in_the_loop.local_chat_ui import ChatUI
from railtracks.llm import ToolCall, ToolResponse

# Text emitted by invoke_tools when a tool raises (llm_helpers.py).
TOOL_ERROR_TEXT = "There was an error during tool execution: ValueError('boom')"


async def test_update_tools_marks_failed_tool_result_as_unsuccessful():
    chat_ui = ChatUI(auto_open=False)

    failed = (
        ToolCall(identifier="bad-id", name="bad_tool", arguments={}),
        ToolResponse(identifier="bad-id", name="bad_tool", result=TOOL_ERROR_TEXT),
    )
    ok = (
        ToolCall(identifier="ok-id", name="ok_tool", arguments={}),
        ToolResponse(identifier="ok-id", name="ok_tool", result="done"),
    )

    assert await chat_ui.update_tools([ok, failed]) is True

    queued = [
        await asyncio.wait_for(chat_ui.sse_queue.get(), timeout=1) for _ in range(2)
    ]
    assert [message["data"]["success"] for message in queued] == [True, False]
