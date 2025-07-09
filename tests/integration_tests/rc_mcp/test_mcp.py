import asyncio
import requestcompletion as rc
from mcp import StdioServerParameters
from requestcompletion.nodes.library.mcp_tool import from_mcp_server
from requestcompletion.nodes.nodes import Node

import pytest
import subprocess
import sys

from requestcompletion.rc_mcp.main import MCPHttpParams


@pytest.fixture(scope="session", autouse=True)
def install_mcp_server_time():
    """Install mcp_server_time and ensure mcp dependency is available.
    
    This fixture ensures that both mcp and mcp_server_time are properly installed,
    which is particularly important on Windows where dependency resolution
    may not work correctly when packages are installed separately.
    """
    try:
        # Install both packages together to ensure proper dependency resolution
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", 
            "mcp>=1.9.0", "mcp_server_time"
        ])
        
        # Verify that the critical modules can be imported
        # This helps catch environment/path issues early
        try:
            import mcp.server  # This is what mcp_server_time needs
            import mcp_server_time
        except ImportError as e:
            pytest.fail(f"MCP packages installed but cannot be imported: {e}")
            
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Failed to install required MCP packages: {e}")


def test_from_mcp_server_basic():
    time_tools = from_mcp_server(
        StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp_server_time", "--local-timezone=America/Vancouver"],
        )
    )
    assert len(time_tools) == 2
    assert all(issubclass(tool, Node) for tool in time_tools)


def test_from_mcp_server_with_llm():
    time_tools = from_mcp_server(
        StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp_server_time", "--local-timezone=America/Vancouver"],
        )
    )
    parent_tool = rc.library.tool_call_llm(
        connected_nodes={*time_tools},
        pretty_name="Parent Tool",
        system_message=rc.llm.SystemMessage(
            "Provide a response using the tool when asked. If the tool doesn't work,"
            " respond with 'It didn't work!'"
        ),
        model=rc.llm.OpenAILLM("gpt-4o"),
    )

    # Run the parent tool
    with rc.Runner(
        executor_config=rc.ExecutorConfig(logging_setting="QUIET", timeout=1000)
    ) as runner:
        message_history = rc.llm.MessageHistory(
            [rc.llm.UserMessage("What time is it?")]
        )
        response = asyncio.run(runner.run(parent_tool, message_history=message_history))

    assert response.answer is not None
    assert response.answer.content != "It didn't work!"


def test_from_mcp_server_with_http():
    time_tools = from_mcp_server(MCPHttpParams(url="https://mcp.deepwiki.com/sse"))
    parent_tool = rc.library.tool_call_llm(
        connected_nodes={*time_tools},
        pretty_name="Parent Tool",
        system_message=rc.llm.SystemMessage(
            "Provide a response using the tool when asked. If the tool doesn't work,"
            " respond with 'It didn't work!'"
        ),
        model=rc.llm.OpenAILLM("gpt-4o"),
    )

    # Run the parent tool
    with rc.Runner(
        executor_config=rc.ExecutorConfig(logging_setting="NONE", timeout=1000)
    ) as runner:
        message_history = rc.llm.MessageHistory(
            [rc.llm.UserMessage("Tell me about the website conductr.ai")]
        )
        response = asyncio.run(runner.run(parent_tool, message_history=message_history))

    assert response.answer is not None
    assert response.answer.content is not "It didn't work!"
