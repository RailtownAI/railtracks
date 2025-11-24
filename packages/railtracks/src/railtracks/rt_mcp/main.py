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
    """
    Configuration parameters for STDIO-based MCP server connections.

    Extends the standard StdioServerParameters with a timeout field.

    Attributes:
        timeout: Maximum time to wait for operations (default: 30 seconds)
    """

    timeout: timedelta = timedelta(seconds=30)

    def as_stdio_params(self) -> StdioServerParameters:
        """
        Convert to standard StdioServerParameters, excluding the timeout field.

        Returns:
            StdioServerParameters without the timeout attribute
        """
        stdio_kwargs = self.dict(exclude={"timeout"})
        return StdioServerParameters(**stdio_kwargs)


class MCPHttpParams(BaseModel):
    """
    Configuration parameters for HTTP-based MCP server connections.

    Supports both SSE (Server-Sent Events) and streamable HTTP transports.
    The transport type is automatically determined based on the URL.

    Attributes:
        url: The MCP server URL (use /sse suffix for SSE transport)
        headers: Optional HTTP headers for authentication
        timeout: Connection timeout (default: 30 seconds)
        sse_read_timeout: SSE read timeout (default: 5 minutes)
        terminate_on_close: Whether to terminate connection on close (default: True)
    """

    url: str
    headers: dict[str, Any] | None = None
    timeout: timedelta = timedelta(seconds=30)
    sse_read_timeout: timedelta = timedelta(seconds=60 * 5)
    terminate_on_close: bool = True


class MCPAsyncClient:
    """
    Async client for communicating with an MCP server.

    Supports both STDIO and HTTP transports with streaming capabilities.
    Manages the connection lifecycle and provides methods for listing and calling tools.

    Attributes:
        config: Connection configuration (MCPStdioParams or MCPHttpParams)
        session: MCP client session (created automatically if not provided)
        exit_stack: Async context manager for resource cleanup

    Note:
        If a client session is provided, it will be used; otherwise, a new session
        will be created automatically based on the config type.
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
        """
        Establish connection to the MCP server.

        Automatically selects the appropriate transport (STDIO or HTTP) based on config type.
        Creates and initializes the client session if one wasn't provided.

        Raises:
            ValueError: If config type is invalid
            Exception: If connection fails (will clean up resources automatically)
        """
        await self.exit_stack.__aenter__()
        self._entered = True
        try:
            if self.session is None:
                if isinstance(self.config, MCPStdioParams):
                    # STDIO transport for local MCP servers
                    stdio_transport = await self.exit_stack.enter_async_context(
                        stdio_client(self.config.as_stdio_params())
                    )
                    self.session = await self.exit_stack.enter_async_context(
                        ClientSession(*stdio_transport)
                    )
                    await self.session.initialize()
                elif isinstance(self.config, MCPHttpParams):
                    # HTTP transport (SSE or streamable HTTP)
                    await self._init_http()
                else:
                    raise ValueError(
                        "Invalid configuration type. Expected MCPStdioParams or MCPHttpParams."
                    )
        except Exception:
            await self.close()
            raise

    async def close(self):
        """Close the connection and clean up resources."""
        if self._entered:
            await self.exit_stack.aclose()
            self._entered = False

    async def list_tools(self):
        """
        List all tools available from the MCP server.

        Results are cached after the first call for efficiency.

        Returns:
            List of available tools
        """
        if self._tools_cache is not None:
            return self._tools_cache
        else:
            resp = await self.session.list_tools()
            self._tools_cache = resp.tools
        return self._tools_cache

    async def call_tool(self, tool_name: str, tool_args: dict):
        """
        Call a specific tool on the MCP server.

        Args:
            tool_name: Name of the tool to call
            tool_args: Arguments to pass to the tool

        Returns:
            Tool execution result
        """
        return await self.session.call_tool(tool_name, tool_args)

    async def _init_http(self):
        """
        Initialize HTTP-based connection (SSE or streamable HTTP).

        Automatically detects transport type based on URL:
        - URLs ending in /sse use Server-Sent Events transport
        - Other URLs use streamable HTTP transport

        Supports optional OAuth authentication via the 'auth' attribute.
        """
        # Determine transport type from URL
        if self.config.url.rstrip("/").endswith("/sse"):
            self.transport_type = "sse"
        else:
            self.transport_type = "streamable_http"

        # Create appropriate client based on transport type
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

        # Initialize session with the client
        read_stream, write_stream, *_ = await self.exit_stack.enter_async_context(
            client
        )
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await self.session.initialize()


class MCPServer:
    """
    Manages connection to an MCP server and provides access to its tools.

    This class handles the connection lifecycle in a background thread, allowing
    synchronous usage of asynchronous MCP operations. Tools are automatically
    discovered and converted to Railtracks Node classes on initialization.

    The connection remains active until explicitly closed or the context manager exits.

    Usage:
        # Direct usage
        server = MCPServer(config=MCPStdioParams(command="python", args=["-m", "mcp_server_time"]))
        tools = server.tools
        server.close()

        # Context manager (recommended)
        with MCPServer(config=config) as server:
            tools = server.tools
            # Use tools...
        # Automatically closed

    Attributes:
        config: Connection configuration (MCPStdioParams or MCPHttpParams)
        tools: List of Node classes representing MCP tools (available after initialization)

    Raises:
        FileNotFoundError: If STDIO command not found
        TimeoutError: If connection setup exceeds timeout
        ConnectionError: If connection to server fails
        RuntimeError: For other setup failures
    """

    def __init__(
        self,
        config: MCPStdioParams | MCPHttpParams,
        client_session: ClientSession | None = None,
        setup_timeout: float = 30,
    ):
        """
        Initialize and connect to an MCP server.

        Connection happens in a background thread to allow sync/async bridging.
        This method blocks until connection is established or timeout occurs.

        Args:
            config: Server configuration (STDIO or HTTP)
            client_session: Optional pre-configured client session
            setup_timeout: Maximum seconds to wait for connection (default: 30)

        Raises:
            FileNotFoundError: If STDIO command not found (with helpful PATH message)
            TimeoutError: If connection setup exceeds timeout
            ConnectionError: If connection to server fails
            RuntimeError: For other setup failures
        """
        self.client = None
        self.config = config
        self.client_session = client_session
        self._tools = None
        self._loop = None
        self._setup_exception = None  # Captures exceptions from background thread
        self._thread = threading.Thread(target=self._thread_main, daemon=True)
        self._ready_event = threading.Event()
        self._shutdown_event = None
        self._thread.start()

        # Wait for background thread to complete setup
        ready = self._ready_event.wait(timeout=setup_timeout)

        if not ready:
            # Setup timed out - clean up and raise error
            self.close()
            raise TimeoutError(
                f"MCP server setup timed out after {setup_timeout} seconds. "
                f"Command: {self.config.command if isinstance(self.config, MCPStdioParams) else self.config.url}"
            )

        # If setup failed with an exception, re-raise it with enhanced context
        if self._setup_exception is not None:
            if isinstance(self._setup_exception, FileNotFoundError):
                if isinstance(self.config, MCPStdioParams):
                    raise FileNotFoundError(
                        f"MCP server command not found: '{self.config.command}'. "
                        f"Please verify the command is installed and in your PATH."
                    ) from self._setup_exception
                else:
                    raise self._setup_exception
            elif isinstance(self._setup_exception, ConnectionError):
                raise ConnectionError(
                    f"Failed to connect to MCP server: {str(self._setup_exception)}"
                ) from self._setup_exception
            else:
                raise RuntimeError(
                    f"MCP server setup failed: {type(self._setup_exception).__name__}: "
                    f"{str(self._setup_exception)}"
                ) from self._setup_exception

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def _thread_main(self):
        """
        Main method for the background thread that manages the async event loop.

        Creates a new event loop, runs the setup process, and waits for shutdown signal.
        Any exceptions during setup are captured and re-raised in __init__.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop

        self._shutdown_event = asyncio.Event()
        try:
            self._loop.run_until_complete(self._setup())
        except asyncio.exceptions.CancelledError:
            # Ensure shutdown event is set so thread can exit cleanly
            loop.call_soon_threadsafe(self._shutdown_event.set)
            raise
        except Exception as e:
            # Capture any exception during setup for re-raising in __init__
            self._setup_exception = e
            # Set shutdown event so thread can exit
            loop.call_soon_threadsafe(self._shutdown_event.set)
        finally:
            # Signal that setup is complete (success or failure)
            self._ready_event.set()
            # Wait for shutdown signal before closing loop
            loop.run_until_complete(self._shutdown_event.wait())
            self._loop.close()

    async def _setup(self):
        """
        Initialize the MCP client connection and fetch available tools.

        This runs once in the background thread when the server is created.
        Tools are converted to Railtracks Node classes for easy integration.

        Raises:
            Exception: Any connection or initialization errors are captured
                      and re-raised in __init__ with enhanced context
        """
        self.client = MCPAsyncClient(self.config, self.client_session)
        await self.client.connect()
        tools = await self.client.list_tools()
        self._tools = [from_mcp(tool, self.client, self._loop) for tool in tools]

    def close(self):
        """
        Close the MCP server connection and clean up resources.

        Signals the background thread to shut down and waits for it to complete.
        Safe to call even if initialization failed early.
        """
        if self._loop is not None and self._shutdown_event is not None:
            self._loop.call_soon_threadsafe(self._shutdown_event.set)
            self._thread.join()

    @property
    def tools(self) -> list[Type[Node]]:
        """
        Get the list of tools available from the MCP server.

        Returns:
            List of Node classes, each representing an MCP tool.
            Each Node has:
            - name(): Tool name
            - tool_info(): Tool metadata (description, parameters)
            - prepare_tool(**kwargs): Create tool instance with arguments
        """
        return self._tools


def from_mcp(
    tool: Tool,
    client: MCPAsyncClient,
    loop: asyncio.AbstractEventLoop,
) -> Type[Node]:
    """
    Convert an MCP tool into a Railtracks Node class.

    Creates a Node subclass that bridges between Railtracks' synchronous API
    and the MCP tool's asynchronous execution. The Node can be used directly
    with rt.call() or passed to agents as a tool.

    Args:
        tool: The MCP tool object with name, description, and schema
        client: Async client for communicating with the MCP server
        loop: Event loop running in the background thread

    Returns:
        A Node subclass that:
        - Implements invoke() to call the MCP tool
        - Provides tool_info() for schema introspection
        - Supports prepare_tool() for argument binding
        - Can be used with rt.call() and agent_node()

    Example:
        server = rt.connect_mcp(config)
        ToolNode = from_mcp(tool, server.client, server._loop)
        result = await rt.call(ToolNode, param1="value1")
    """

    class MCPToolNode(Node):
        """Dynamic Node class representing an MCP tool."""

        def __init__(self, **kwargs):
            """Initialize with tool arguments."""
            super().__init__()
            self.kwargs = kwargs

        def invoke(self):
            """
            Execute the MCP tool with the provided arguments.

            Bridges from sync to async by running the tool call in the
            background thread's event loop and waiting for the result.

            Returns:
                The tool's execution result

            Raises:
                RuntimeError: If tool execution fails
            """
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
            """Return the tool name."""
            return tool.name

        @classmethod
        def tool_info(cls) -> Tool:
            """
            Get tool metadata including parameters and description.

            Returns:
                Tool object with name, description, and parameter schemas
            """
            return Tool.from_mcp(tool)

        @classmethod
        def prepare_tool(cls, **kwargs) -> Self:
            """
            Create a tool instance with bound arguments.

            Args:
                **kwargs: Arguments to pass to the tool

            Returns:
                Tool instance ready for execution
            """
            return cls(**kwargs)

        @classmethod
        def type(cls):
            """Return the node type identifier."""
            return "Tool"

    return MCPToolNode
