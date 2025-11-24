from mcp import ClientSession

from .jupyter_compat import apply_patches
from .main import MCPHttpParams, MCPServer, MCPStdioParams


def connect_mcp(
    config: MCPStdioParams | MCPHttpParams,
    client_session: ClientSession | None = None,
    setup_timeout: float = 30,
) -> MCPServer:
    """
    Connect to an MCP server and return a server instance with available tools.

    This is the primary entry point for using MCP servers in Railtracks.
    The server will connect in the background, discover available tools,
    and convert them to Railtracks Node classes.

    The connection remains active until explicitly closed or the context exits.

    Usage Examples:
        # STDIO connection (local MCP server)
        config = rt.MCPStdioParams(
            command="uvx",
            args=["mcp-server-time"]
        )
        server = rt.connect_mcp(config)

        # HTTP connection (remote MCP server)
        config = rt.MCPHttpParams(
            url="https://mcp.example.com/sse",
            headers={"Authorization": "Bearer token"}
        )
        server = rt.connect_mcp(config)

        # Context manager (recommended)
        with rt.connect_mcp(config) as server:
            tools = server.tools
            # Use tools...
        # Automatically closed

        # Access tools
        for tool in server.tools:
            print(f"Tool: {tool.name()}")
            print(f"Description: {tool.tool_info().description}")

    Args:
        config: Server configuration:
            - MCPStdioParams: For local servers via stdin/stdout
            - MCPHttpParams: For remote servers via HTTP/SSE
        client_session: Optional pre-configured ClientSession for advanced use cases.
                       If not provided, a new session will be created automatically.
        setup_timeout: Maximum seconds to wait for connection (default: 30).
                      Increase for slow servers or complex authentication flows.

    Returns:
        MCPServer: Connected server instance with:
            - tools: List of Node classes representing MCP tools
            - close(): Method to explicitly close the connection
            - Context manager support for automatic cleanup

    Raises:
        FileNotFoundError: If STDIO command not found. Verify the command is:
                          - Installed and in your PATH
                          - Spelled correctly (check for typos)
                          - Executable (check permissions on Unix)
        ConnectionError: If connection to server fails. Check:
                        - Server URL is correct and accessible
                        - Network connectivity and firewall settings
                        - Authentication credentials are valid
                        - Server is running and accepting connections
        TimeoutError: If connection exceeds setup_timeout. Try:
                     - Increasing setup_timeout parameter
                     - Checking server performance/load
                     - Verifying server is responding
        RuntimeError: For other setup failures (e.g., protocol errors, config issues)

    Note:
        - The connection runs in a background thread for sync/async bridging
        - Tools are cached after first retrieval for performance
        - Always close() the server when done or use context manager
        - Jupyter compatibility patches are applied automatically
    """
    # Apply Jupyter compatibility patches if needed
    apply_patches()

    return MCPServer(
        config=config, client_session=client_session, setup_timeout=setup_timeout
    )
