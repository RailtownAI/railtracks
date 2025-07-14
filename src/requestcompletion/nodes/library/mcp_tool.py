from mcp import StdioServerParameters

from ...rc_mcp.main import MCPHttpParams, MCPServer


def from_mcp_server(
    config: StdioServerParameters | MCPHttpParams,
) -> MCPServer:
    """
    Returns an MCPServer class. On creation, it will connect to the MCP server and fetch the tools.
    The connection will remain open until the server is closed with `close()`.

    Args:
        config: Configuration for the MCP server, either as StdioServerParameters or MCPHttpParams.

    Returns:
        MCPServer: An instance of the MCPServer class.
    """
    return MCPServer(config=config)
