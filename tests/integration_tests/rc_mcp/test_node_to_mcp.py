import asyncio

import threading
import time

import pytest

import requestcompletion as rc
from requestcompletion.rc_mcp import MCPHttpParams
from requestcompletion.rc_mcp.to_node import create_mcp_server
from requestcompletion.nodes import library as rc_library

from mcp.server import FastMCP

import socket
import pytest


# --------------------------------------------------------------------------- #
#                         Helper: get the next free port                      #
# --------------------------------------------------------------------------- #
def get_free_port(start_from: int = 8000, upper_bound: int = 50_000) -> int:
    """
    Returns the first TCP port ≥ start_from that is currently free.
    """
    port = start_from
    while port <= upper_bound:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                # if bind succeeds the port is free; immediately close the socket
                return port
            except OSError:
                port += 1
    raise RuntimeError("Could not find a free port in the requested range")


if __name__ == "__main__":
    # Example usage
    try:
        free_port = get_free_port()
        print(f"Found free port: {free_port}")
    except RuntimeError as e:
        print(e)


def add_nums(num1: int, num2: int, print_s: str):
    """Function we expose as a tool."""
    return num1 + num2 + 10


node = rc_library.from_function(add_nums)

FAST_MCP_PORT = get_free_port(8000)


def run_server():
    """
    Starts the MCP server in the current (background) thread
    and blocks for the lifetime of the process.
    """
    fast_mcp = FastMCP(port=FAST_MCP_PORT)
    mcp = create_mcp_server([node], fastmcp=fast_mcp, server_name="Test MCP Server")

    # Most recent versions of `streamable-http`/`FastAPI`-backed transports expose
    # `host`/`port` kwargs.  If yours does not, adapt accordingly.
    mcp.run(transport="streamable-http")


@pytest.fixture(scope="module")
def mcp_server():
    """Spin up the MCP server once per test module."""
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()

    # Give it a moment to boot; in CI you might poll instead of sleeping.
    time.sleep(3)
    yield


# --------------------------------------------------------------------------- #
#                                    Tests                                    #
# --------------------------------------------------------------------------- #
def test_add_nums_tool(mcp_server):
    tools = rc_library.from_mcp_server(
        MCPHttpParams(url=f"http://127.0.0.1:{FAST_MCP_PORT}/mcp")
    )
    assert len(tools) == 1

    with rc.Runner(
        executor_config=rc.ExecutorConfig(logging_setting="QUIET", timeout=1000)
    ) as runner:
        response = asyncio.run(runner.run(tools[0], num1=1, num2=3, print_s="Hello"))

    assert (
        response.answer[0].text == "14"
    ), f"Expected 14, got {response.answer[0].text}"


# --------------------------------------------------------------------------- #
#             Allow running this file directly for manual debugging           #
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    run_server()
