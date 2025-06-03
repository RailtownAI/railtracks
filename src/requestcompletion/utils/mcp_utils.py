import inspect
from contextlib import AsyncExitStack
from datetime import timedelta
from typing import Any, Dict
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.sse import sse_client
from mcp.shared.exceptions import McpError
from pydantic import BaseModel
from requestcompletion.llm import Tool
from requestcompletion.nodes.nodes import Node
from typing_extensions import Self, Union

try:
    from sseclient import SSEClient
except ImportError:
    SSEClient = None


class MCPHttpParams(BaseModel):
    url: str
    headers: dict[str, Any] | None = None
    timeout: timedelta = timedelta(seconds=30)
    sse_read_timeout: timedelta = timedelta(seconds=60 * 5)
    terminate_on_close: bool = True


class MCPAsyncClient:
    """
    Async client for communicating with an MCP server via stdio or HTTP Stream, with streaming support.
    """

    def __init__(
        self,
        config: Union[StdioServerParameters, MCPHttpParams],
    ):
        self.config = config
        self.session = None
        self.exit_stack = AsyncExitStack()
        self._tools_cache = None
        self.sse_client = False

        # If config is HTTP and url ends with /sse, set sse_client flag to True
        if isinstance(self.config, MCPHttpParams):
            if self.config.url.rstrip("/").endswith("/sse"):
                self.sse_client = True

    async def __aenter__(self):
        if isinstance(self.config, StdioServerParameters):
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(self.config))
            self.session = await self.exit_stack.enter_async_context(ClientSession(*stdio_transport))
            await self.session.initialize()
        elif isinstance(self.config, MCPHttpParams):

            if not self.sse_client:
                try:
                    await self._init_session(streamablehttp_client)
                except Exception:  # McpError
                    await self._init_session(sse_client)
                    self.sse_client = True
            else:
                await self._init_session(sse_client)

        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.exit_stack.aclose()

    async def _init_session(self, client_factory):
        sig = inspect.signature(client_factory)
        accepted_params = set(sig.parameters.keys())

        # Prepare kwargs from self.config
        config_dict = self.config.__dict__
        filtered_kwargs = {}

        for k, v in config_dict.items():
            if k in sig.parameters:
                param = sig.parameters[k]
                expected_type = param.annotation
                # Convert timedelta to float if needed
                if expected_type is float and isinstance(v, timedelta):
                    filtered_kwargs[k] = v.total_seconds()
                # Convert float to timedelta if needed
                elif expected_type is timedelta and isinstance(v, (int, float)):
                    filtered_kwargs[k] = timedelta(seconds=v)
                else:
                    filtered_kwargs[k] = v


        # Call client_factory with only accepted kwargs
        read_stream, write_stream, *_ = await self.exit_stack.enter_async_context(
            client_factory(**filtered_kwargs)
        )
        self.session = await self.exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
        await self.session.initialize()

    async def list_tools(self):
        if self._tools_cache is not None:
            return self._tools_cache
        else:
            resp = await self.session.list_tools()
            self._tools_cache = resp.tools
            
        return self._tools_cache

    async def call_tool(self, tool_name: str, tool_args: dict):
        return await self.session.call_tool(tool_name, tool_args)


def from_mcp( # noqa: C901
    tool,
    config: Union[StdioServerParameters, MCPHttpParams],
):
    """
    Wrap an MCP tool as a Node class for use in the requestcompletion framework.

    Args:
        tool: The MCP tool object.
        config: Configuration parameters for the MCP client, either Stdio or HTTP.

    Returns:
        A Node subclass that invokes the MCP tool.
    """

    class MCPToolNode(Node):
        def __init__(self, **kwargs):
            super().__init__()
            self.kwargs = kwargs
            self.client = MCPAsyncClient(config)

        async def invoke(self):
            async with self.client:
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
