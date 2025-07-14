
from mcp import StdioServerParameters

from ...rc_mcp.main import MCPHttpParams, MCPServer


def from_mcp_server(
    config: StdioServerParameters | MCPHttpParams,
) -> MCPServer:
    """
    Discover all tools from an MCP server and wrap them as Node classes.

    Args:
        config: Configuration for the MCP server, either as StdioServerParameters or MCPHttpParams.

    Returns:
        List of Nodes, one for each discovered tool.
    """
    return MCPServer(config=config)
