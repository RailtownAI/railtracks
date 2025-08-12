# Node to MCP Server

The Node to MCP Server component is designed to create a FastMCP server that registers and runs nodes as MCP tools, enabling asynchronous tool execution within the system.

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

The primary purpose of this component is to facilitate the integration of nodes as tools within a FastMCP server, allowing for their asynchronous execution. This is particularly useful in scenarios where multiple nodes need to be managed and executed concurrently, leveraging the capabilities of the FastMCP framework.

### 1.1 Registering Nodes as MCP Tools

This use case involves registering a list of nodes as tools within a FastMCP server. This is crucial for enabling the nodes to be executed asynchronously as part of the server's operations.

python
from railtracks.rt_mcp.node_to_mcp import create_mcp_server
from railtracks.nodes.nodes import Node

# Define your nodes
nodes = [Node1(), Node2()]

# Create the MCP server
mcp_server = create_mcp_server(nodes, server_name="My MCP Server")


## 2. Public API

### `def create_mcp_server(nodes, server_name, fastmcp)`
Create a FastMCP server that can be used to run nodes as MCP tools.

Args:
    nodes: List of Node classes to be registered as tools with the MCP server.
    server_name: Name of the MCP server instance.
    fastmcp: Optional FastMCP instance to use instead of creating a new one.

Returns:
    A FastMCP server instance.


---

## 3. Architectural Design

The Node to MCP Server component is designed with the following architectural principles:

### 3.1 Core Design Principles

- **Asynchronous Execution:** The component leverages asynchronous programming to allow nodes to be executed concurrently, improving performance and scalability.
- **Modular Design:** The component is structured to separate concerns, with distinct functions for creating tool functions and the MCP server.

### 3.2 High-Level Architecture

The component consists of two main functions:

- **`_create_tool_function`:** This function generates a tool function for each node, using the node's metadata to define parameters and documentation.
- **`create_mcp_server`:** This function initializes a FastMCP server and registers each node as a tool, using the tool functions created by `_create_tool_function`.

### 3.3 Key Design Decisions

- **Use of FastMCP:** The decision to use FastMCP was driven by its robust support for asynchronous tool execution and management.
- **Parameter Schema Handling:** The component uses `_parameters_to_json_schema` to convert node parameters into a JSON schema, ensuring consistent parameter handling.

## 4. Important Considerations

### 4.1 Dependencies & Setup

- **FastMCP Dependency:** The component relies on the FastMCP library for server and tool management. Ensure that FastMCP is installed and properly configured.
- **Node Class Requirements:** Nodes must implement the `tool_info` method to provide necessary metadata for registration.

### 4.2 Performance & Limitations

- **Scalability:** The component is designed to handle multiple nodes, but performance may degrade with a very large number of nodes due to resource constraints.

## 5. Related Files

### 5.1 Code Files

- [`../packages/railtracks/src/railtracks/rt_mcp/node_to_mcp.py`](../packages/railtracks/src/railtracks/rt_mcp/node_to_mcp.py): Contains the implementation of the Node to MCP Server component.

### 5.2 Related Component Files

- [MCP Tool Connection Documentation](../components/mcp_tool_connection.md): Provides additional context on how MCP tools are connected and managed.

### 5.3 Related Feature Files

- [MCP Integration Documentation](../features/mcp_integration.md): Discusses the broader integration of MCP within the system.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
