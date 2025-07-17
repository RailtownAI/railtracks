from mcp import ClientSession

from ...rc_mcp.main import MCPHttpParams, MCPServer, MCPStdioParams


def from_mcp_server(
    config: MCPStdioParams | MCPHttpParams, client_session: ClientSession | None = None
) -> MCPServer:
    """
    Returns an MCPServer class. On creation, it will connect to the MCP server and fetch the tools.
    The connection will remain open until the server is closed with `close()`.

    Args:
        config: Configuration for the MCP server, either as StdioServerParameters or MCPHttpParams.
        client_session: Optional ClientSession to use for the MCP server connection. If not provided, a new session will be created.

    Returns:
        MCPServer: An instance of the MCPServer class.
    """
    return MCPServer(config=config, client_session=client_session)
