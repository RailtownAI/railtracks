# Exposing RT Tools as MCP Tools

## Overview

You can expose any RT Tool as an MCP-compatible tool, making it accessible to any MCP client or LLM agent that supports the [Model Context Protocol (MCP)](index.md). This allows you to share your custom RT logic with other frameworks, agents, or applications that use MCP.

RC provides utilities to convert your Nodes into MCP tools and run a FastMCP server, so your tools are discoverable and callable via standard MCP transports (HTTP, SSE, stdio).

## Prerequisites

- **RC Framework** installed (`pip install railtracks`)

## Basic Usage

### 1. Convert RT Nodes to MCP Tools

Use the `create_mcp_server` utility to expose your RT nodes as MCP tools:

```python
from railtracks.nodes.library import from_function
from railtracks.rt_mcp.to_node import create_mcp_server

def add_nums_plus_ten(num1: int, num2: int):
    """Simple tool example."""
    return num1 + num2 + 10

node = from_function(add_nums_plus_ten)

# Create and run the MCP server
mcp = create_mcp_server([node], server_name="My MCP Server")
mcp.run(transport="streamable-http", host="127.0.0.1", port=8000)
```

This exposes your RT tool at `http://127.0.0.1:8000/mcp` for any MCP client.

### 2. Accessing Your MCP Tools

Any MCP-compatible client or LLM agent can now discover and invoke your tool. As an example, you can use R C itself to try your tool:

```python
from railtracks.nodes.library.mcp_tool import from_mcp_server
from railtracks.rt_mcp.main import MCPHttpParams

server = from_mcp_server(MCPHttpParams(url="http://127.0.0.1:8000/mcp"))
tools = server.tools
```

## Advanced Topics

- **Multiple Tools:** Pass a list of Node classes to `create_mcp_server` to expose several tools.
- **Transport Options:** Use `streamable-http`, `sse`, or `stdio` as needed.

## Related Topics

- [What is MCP?](index.md)
- [Using MCP Tools in RT](MCP_tools_in_rt.md)
