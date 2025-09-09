# Exposing RT Tools as MCP Tools

!!! Warning 
    This area of RT is under construction. We would love some contributions to support this effort on our [Github](https://github.com/RailtownAI/railtracks)

## Overview

You can expose any RT Tool as an MCP-compatible tool, making it accessible to any MCP client or LLM agent that supports the [Model Context Protocol (MCP)](mcp.md). This allows you to share your custom RT logic with other frameworks, agents, or applications that use MCP.

RC provides utilities to convert your Nodes into MCP tools and run a FastMCP server, so your tools are discoverable and callable via standard MCP transports (HTTP, SSE, stdio).

## Prerequisites

- **RC Framework** installed (`pip install railtracks[core]`)

## Basic Usage

### 1. Convert RT Nodes to MCP Tools

Use the `create_mcp_server` utility to expose your RT nodes as MCP tools:

```python
--8<-- "docs/scripts/RTtoMCP.py:simple_mcp_creation"
```

This exposes your RT tool at `http://127.0.0.1:8000/mcp` for any MCP client.

### 2. Accessing Your MCP Tools

Any MCP-compatible client or LLM agent can now discover and invoke your tool. As an example, you can use Railtracks itself to try your tool:

```python
--8<-- "docs/scripts/RTtoMCP.py:accessing_mcp"
```

## Advanced Topics

- **Multiple Tools:** Pass a list of Node classes to `create_mcp_server` to expose several tools.
- **Transport Options:** Use `streamable-http`, `sse`, or `stdio` as needed.

## Related Topics

- [What is MCP?](mcp.md)
- [Using MCP Tools in RT](MCP_tools_in_RT.md)
