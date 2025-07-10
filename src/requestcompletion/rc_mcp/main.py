from contextlib import AsyncExitStack
from datetime import timedelta
from typing import Any, Dict

from typing_extensions import Self

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.sse import sse_client

from pydantic import BaseModel
from ..llm import Tool
from ..nodes.nodes import Node


class MCPHttpParams(BaseModel):
    url: str
    headers: dict[str, Any] | None = None
    timeout: timedelta = timedelta(seconds=30)
    sse_read_timeout: timedelta = timedelta(seconds=60 * 5)
    terminate_on_close: bool = True


class MCPAsyncClient:
    """
    Async client for communicating with an MCP server via stdio or HTTP Stream, with streaming support.

    If a client session is provided, it will be used; otherwise, a new session will be created.
    """

    def __init__(
        self,
        config: StdioServerParameters | MCPHttpParams,
        client_session: ClientSession | None = None,
    ):
        self.config = config
        self.session = client_session
        self.exit_stack = AsyncExitStack()
        self._tools_cache = None

    async def __aenter__(self):
        if self.session is None:
            if isinstance(self.config, StdioServerParameters):
                stdio_transport = await self.exit_stack.enter_async_context(
                    stdio_client(self.config)
                )
                self.session = await self.exit_stack.enter_async_context(
                    ClientSession(*stdio_transport)
                )
                await self.session.initialize()
            elif isinstance(self.config, MCPHttpParams):
                await self._init_http()

        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.exit_stack.aclose()

    async def list_tools(self):
        if self._tools_cache is not None:
            return self._tools_cache
        else:
            resp = await self.session.list_tools()
            self._tools_cache = resp.tools
        return self._tools_cache

    async def call_tool(self, tool_name: str, tool_args: dict):
        return await self.session.call_tool(tool_name, tool_args)

    async def _init_http(self):
        # Set transport type based on URL ending
        if self.config.url.rstrip("/").endswith("/sse"):
            self.transport_type = "sse"
        else:
            self.transport_type = "streamable_http"

        if self.transport_type == "sse":
            client = sse_client(
                url=self.config.url,
                headers=self.config.headers,
                timeout=self.config.timeout.total_seconds(),
                sse_read_timeout=self.config.sse_read_timeout.total_seconds(),
                auth=self.config.auth if hasattr(self.config, "auth") else None,
            )
        else:
            client = streamablehttp_client(
                url=self.config.url,
                headers=self.config.headers,
                timeout=self.config.timeout.total_seconds(),
                sse_read_timeout=self.config.sse_read_timeout.total_seconds(),
                terminate_on_close=self.config.terminate_on_close,
                auth=self.config.auth if hasattr(self.config, "auth") else None,
            )

        read_stream, write_stream, *_ = await self.exit_stack.enter_async_context(
            client
        )
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await self.session.initialize()


class MCPServer:
    """
    Class representation for MCP server

    This class contains the tools of the MCP server and manages the connection to the server.

    On initialization, it will connect to the MCP server, and will remain connected until closed.
    """

    def __init__(self, client: MCPAsyncClient):
        self.client = client
        self._tools = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.client.__aexit__(exc_type, exc, tb)

    async def setup(self):
        """
        Set up the MCP server and fetch tools.
        """
        await self.client.__aenter__()
        self._tools = [from_mcp(tool, self.client) for tool in await self.client.list_tools()]

    @property
    def tools(self):
        return self._tools


def from_mcp(
    tool,
    client,
):
    """
    Wrap an MCP tool as a Node class for use in the requestcompletion framework.

    Args:
        tool: The MCP tool object.
        client: An instance of MCPAsyncClient to communicate with the MCP server.

    Returns:
        A Node subclass that invokes the MCP tool.
    """

    class MCPToolNode(Node):
        def __init__(self, **kwargs):
            super().__init__()
            self.kwargs = kwargs
            self.client = client

        async def invoke(self):
            result = await self.client.call_tool(tool.name, self.kwargs)
            if hasattr(result, "content"):
                return result.content
            return result

        @classmethod
        def pretty_name(cls):
            return f"MCPToolNode({tool.name})"

        @classmethod
        def tool_info(cls) -> Tool:
            return Tool.from_mcp(tool)

        @classmethod
        def prepare_tool(cls, tool_parameters: Dict[str, Any]) -> Self:
            return cls(**tool_parameters)

    return MCPToolNode
