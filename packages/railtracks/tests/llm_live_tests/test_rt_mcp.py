import asyncio

import pytest

import railtracks as rt

import sys

from railtracks.rt_mcp.main import MCPHttpParams, MCPStdioParams


@pytest.mark.skip(reason="Skipped due to LLM stochasticity")
def test_from_mcp_server_with_llm():
    time_server = rt.connect_mcp(
        MCPStdioParams(
            command=sys.executable,
            args=["-m", "mcp_server_time", "--local-timezone=America/Vancouver"],
        )
    )
    parent_tool = rt.agent_node(
        tool_nodes={*time_server.tools},
        name="Parent Tool",
        system_message=(
            "Provide a response using the tool when asked. If the tool doesn't work,"
            " respond with 'It didn't work!'"
        ),
        llm=rt.llm.OpenAILLM("gpt-4o"),
    )

    # Run the parent tool
    with rt.Session(
        logging_setting="NONE", timeout=1000
    ):
        message_history = rt.llm.MessageHistory(
            [rt.llm.UserMessage("What time is it?")]
        )
        response = asyncio.run(rt.call(parent_tool, user_input=message_history))

    assert response is not None
    assert response.content != "It didn't work!"


@pytest.mark.skip(reason="Skipped due to LLM stochasticity")
def test_from_mcp_server_with_http():
    time_server = rt.connect_mcp(MCPHttpParams(url="https://mcp.deepwiki.com/sse"))
    parent_tool = rt.agent_node(
        tool_nodes={*time_server.tools},
        name="Parent Tool",
        system_message=(
            "Provide a response using the tool when asked. If the tool doesn't work,"
            " respond with 'It didn't work!'"
        ),
        llm=rt.llm.OpenAILLM("gpt-4o"),
    )

    # Run the parent tool
    with rt.Session(
        logging_setting="NONE", timeout=1000
    ):
        message_history = rt.llm.MessageHistory(
            [rt.llm.UserMessage("Tell me about the website conductr.ai")]
        )
        response = asyncio.run(rt.call(parent_tool, user_input=message_history))

    assert response is not None
    assert response.content is not "It didn't work!"