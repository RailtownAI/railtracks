import asyncio
import threading
from contextlib import AsyncExitStack
from datetime import timedelta
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from pydantic import BaseModel
from typing_extensions import Self, Type

from railtracks.llm import Tool
from railtracks.nodes.nodes import Node


class MCPStdioParams(StdioServerParameters):
    timeout: timedelta = timedelta(seconds=30)

    def as_stdio_params(self) -> StdioServerParameters:
        # Collect all attributes except 'timeout'
        stdio_kwargs = self.dict(exclude={"timeout"})
        return StdioServerParameters(**stdio_kwargs)


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
        config: MCPStdioParams | MCPHttpParams,
        client_session: ClientSession | None = None,
    ):
        self.config = config
        self.session = client_session
        self.exit_stack = AsyncExitStack()
        self._entered = False
        self._tools_cache = None

    async def connect(self):
        await self.exit_stack.__aenter__()
        self._entered = True
        try:
            if self.session is None:
                if isinstance(self.config, MCPStdioParams):
                    stdio_transport = await self.exit_stack.enter_async_context(
                        stdio_client(self.config.as_stdio_params())
                    )
                    self.session = await self.exit_stack.enter_async_context(
                        ClientSession(*stdio_transport)
                    )
                    await self.session.initialize()
                elif isinstance(self.config, MCPHttpParams):
                    await self._init_http()
                else:
                    raise ValueError(
                        "Invalid configuration type. Expected MCPStdioParams or MCPHttpParams."
                    )
        except Exception:
            await self.close()
            raise

    async def close(self):
        if self._entered:
            await self.exit_stack.aclose()
            self._entered = False

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

    def __init__(
        self,
        config: MCPStdioParams | MCPHttpParams,
        client_session: ClientSession | None = None,
    ):
        self.client = None
        self.config = config
        self.client_session = client_session
        self._tools = None
        self._loop = None
        self._thread = threading.Thread(target=self._thread_main, daemon=True)
        self._ready_event = threading.Event()
        self._shutdown_event = None
        self._thread.start()
        self._ready_event.wait()  # Wait for thread to finish setup

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def _thread_main(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop

        self._shutdown_event = asyncio.Event()
        try:
            self._loop.run_until_complete(self._setup())
        except asyncio.exceptions.CancelledError as e:
            # Ensure shutdown event is set so thread can exit
            loop.call_soon_threadsafe(self._shutdown_event.set)
            raise e
            # Optionally log or handle the error
        finally:
            self._ready_event.set()
            loop.run_until_complete(self._shutdown_event.wait())
            self._loop.close()

    async def _setup(self):
        """
        Set up the MCP server and fetch tools. This is run once, when the thread starts.
        """
        self.client = MCPAsyncClient(self.config, self.client_session)
        await self.client.connect()
        tools = await self.client.list_tools()
        self._tools = [from_mcp(tool, self.client, self._loop) for tool in tools]

    def close(self):
        """
        Close the MCP server connection.
        """
        self._loop.call_soon_threadsafe(self._shutdown_event.set)
        self._thread.join()

    @property
    def tools(self) -> list[Type[Node]]:
        """Returns a list of Tool Nodes available in the MCP server."""
        return self._tools


def from_mcp(
    tool: Tool,
    client: MCPAsyncClient,
    loop: asyncio.AbstractEventLoop,
) -> Type[Node]:
    """
    Wrap an MCP tool as a Node class for use in the railtracks framework.

    Args:
        tool: The MCP tool object.
        client: An instance of MCPAsyncClient to communicate with the MCP server.
        loop: The asyncio event loop to use for running the tool.

    Returns:
        A Node subclass that invokes the MCP tool.
    """

    class MCPToolNode(Node):
        def __init__(self, **kwargs):
            super().__init__()
            self.kwargs = kwargs

        def invoke(self):
            try:
                future = asyncio.run_coroutine_threadsafe(
                    client.call_tool(tool.name, self.kwargs), loop
                )
                result = future.result(timeout=client.config.timeout.total_seconds())
                return result
            except Exception as e:
                raise RuntimeError(
                    f"Tool invocation failed: {type(e).__name__}: {str(e)}"
                ) from e

        @classmethod
        def name(cls):
            return tool.name

        @classmethod
        def tool_info(cls) -> Tool:
            return Tool.from_mcp(tool)

        @classmethod
        def prepare_tool(cls, **kwargs) -> Self:
            return cls(**kwargs)

        @classmethod
        def type(cls):
            return "Tool"

    return MCPToolNode
