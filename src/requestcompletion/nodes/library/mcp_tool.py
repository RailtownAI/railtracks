from typing import Type

from mcp import StdioServerParameters
import asyncio

from ...rc_mcp.main import MCPAsyncClient, MCPHttpParams, from_mcp, MCPServer
from ...nodes.nodes import Node


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
    return MCPServer(client=MCPAsyncClient, config=config)


async def async_from_mcp_server(
    config: StdioServerParameters | MCPHttpParams,
) -> MCPServer:
    """
    Asynchronously discover all tools from an MCP server and wrap them as Node classes.

    Args:
        config

    Returns:
        List of Nodes, one for each discovered tool.
    """
    server = MCPServer(client=MCPAsyncClient(config))
    await server.setup()
    return server
