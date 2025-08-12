# MCP Tool Connection

The MCP Tool Connection component provides a function to establish a connection to an MCP server using specified configuration parameters. It is a crucial part of the system that facilitates communication with the MCP server, enabling the retrieval and management of tools.

**Version:** 0.0.1

**Component Contact:** @developer_username

## Table of Contents

- [1. Purpose](#1-purpose)
- [2. Public API](#2-public-api)
- [3. Architectural Design](#3-architectural-design)
- [4. Important Considerations](#4-important-considerations)
- [5. Related Files](#5-related-files)
- [CHANGELOG](#changelog)

## 1. Purpose

The primary purpose of the MCP Tool Connection component is to establish and manage a connection to an MCP server. This connection allows for the fetching and utilization of tools hosted on the server, which are essential for various operations within the system.

### 1.1 Establishing a Connection

The component provides a straightforward interface to connect to an MCP server using either standard input/output parameters or HTTP parameters. This flexibility is important for accommodating different server configurations and communication protocols.

python
from mcp_tool import connect_mcp
from mcp import ClientSession
from main import MCPHttpParams, MCPStdioParams

# Example of connecting using HTTP parameters
http_config = MCPHttpParams(url="http://example.com", token="your_token")
server = connect_mcp(config=http_config)

# Example of connecting using Stdio parameters
stdio_config = MCPStdioParams(stdin="input", stdout="output")
server = connect_mcp(config=stdio_config)


## 2. Public API

### `def connect_mcp(config, client_session)`
Returns an MCPServer class. On creation, it will connect to the MCP server and fetch the tools.
The connection will remain open until the server is closed with `close()`.

Args:
    config: Configuration for the MCP server, either as StdioServerParameters or MCPHttpParams.
    client_session: Optional ClientSession to use for the MCP server connection. If not provided, a new session will be created.

Returns:
    MCPServer: An instance of the MCPServer class.


---

## 3. Architectural Design

The design of the MCP Tool Connection component is centered around flexibility and ease of use. It leverages the `MCPServer` class to manage the server connection and tool retrieval process.

### 3.1 Connection Management

- **MCPServer Class**: This class is responsible for maintaining the connection to the MCP server. It is designed to keep the connection open until explicitly closed by the user, ensuring persistent communication.
- **Configuration Flexibility**: The component supports both `MCPStdioParams` and `MCPHttpParams` for configuration, allowing it to adapt to different server setups and communication needs.

## 4. Important Considerations

### 4.1 Dependencies & Setup

- **ClientSession**: The component optionally uses a `ClientSession` from the `mcp` module to manage HTTP connections. If not provided, a new session is created internally.
- **Jupyter Compatibility**: The component applies Jupyter compatibility patches using the `apply_patches` function, ensuring smooth operation within Jupyter environments.

### 4.2 Performance & Limitations

- **Persistent Connection**: The connection remains open until the `MCPServer` is closed, which may have implications for resource usage and should be managed appropriately.

## 5. Related Files

### 5.1 Code Files

- [`mcp_tool.py`](../packages/railtracks/src/railtracks/rt_mcp/mcp_tool.py): Contains the implementation of the `connect_mcp` function and related logic.

### 5.2 Related Component Files

- [`mcp_client_server.md`](../components/mcp_client_server.md): Provides documentation on the MCP client-server architecture and its integration with this component.

### 5.3 Related Feature Files

- [`mcp_integration.md`](../features/mcp_integration.md): Details the integration of MCP tools within the broader system, including usage scenarios and configuration.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
