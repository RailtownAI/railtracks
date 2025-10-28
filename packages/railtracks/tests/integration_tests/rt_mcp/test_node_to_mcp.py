import socket
import threading
import time

import pytest
import railtracks as rt
from mcp.server import FastMCP
from railtracks.rt_mcp import MCPHttpParams, connect_mcp, create_mcp_server


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


node = rt.function_node(add_nums)

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
@pytest.mark.asyncio
async def test_add_nums_tool(mcp_server):
    server = connect_mcp(MCPHttpParams(url=f"http://127.0.0.1:{FAST_MCP_PORT}/mcp"))
    assert len(server.tools) == 1

    with rt.Session(logging_setting="CRITICAL", timeout=1000):
        response = await rt.call(server.tools[0], num1=1, num2=3, print_s="Hello")

    print(response.content)
    assert response.content[0].text == "14", (
        f"Expected 14, got {response.content[0].text}"
    )



