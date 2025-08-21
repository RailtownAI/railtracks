import asyncio
import time

import railtracks as rt
from railtracks.nodes.nodes import Node

import pytest
import subprocess
import sys

from railtracks.rt_mcp.main import MCPHttpParams, MCPStdioParams


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
    time_server = rt.connect_mcp(
        MCPStdioParams(
            command=sys.executable,
            args=["-m", "mcp_server_time", "--local-timezone=America/Vancouver"],
        )
    )
    assert len(time_server.tools) == 2
    assert all(issubclass(tool, Node) for tool in time_server.tools)



class MockClient:
    def __init__(self, delay=1):
        self.delay = delay

    async def call_tool(self, tool_name, kwargs):
        await asyncio.sleep(self.delay)
        return f"done {tool_name}"

    async def list_tools(self):
        Tool = type("Tool", (), {
            "name": "tool1",
            "description": "Mock tool 1",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        })
        Tool2 = type("Tool", (), {
            "name": "tool2",
            "description": "Mock tool 2",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        })
        return type("ToolResponse", (), {"tools": [Tool, Tool2]})()


@pytest.mark.asyncio
async def test_parallel_mcp_servers():
    client = MockClient()
    client2 = MockClient()
    server1 = rt.connect_mcp(MCPHttpParams(url=""), client).tools[0]
    server2 = rt.connect_mcp(MCPHttpParams(url=""), client2).tools[1]

    start = time.perf_counter()
    results = await asyncio.gather(rt.call(server1), rt.call(server2))
    elapsed = time.perf_counter() - start

    assert all("done" in r for r in results)
    assert elapsed < 2
