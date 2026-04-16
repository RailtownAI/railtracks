!!! Warning 
    The `Model Context Protocol` was developed and adopted rapidly in late 2024/early 2025. It's seeming that the field is now focusing on tools and skills due to more efficent token context usage. Therefore this area of Railtracks is in a low maintenance state. If there are any required features needed please open an issue at [Github](https://github.com/RailtownAI/railtracks/issues)

## 1. Using MCP Tools in Railtracks

### Overview

!!! tip "Quick Summary"
    Railtracks makes it easy to use any MCP-compatible tool with your agents. Just connect to an MCP server, get the tools, and start using them!

Railtracks supports integration with [Model Context Protocol (MCP)](mcp.md), allowing you to use any MCP-compatible tool as a native Railtracks Tool. This means you can connect your agents to a wide variety of external tools and data sources—without having to implement the tool logic yourself. 

Railtracks handles the discovery and invocation of MCP tools, so you can focus on building intelligent agents.

### Prerequisites

!!! note "Before You Begin"
    Make sure you have the following set up before using MCP tools:

    - **Railtracks Framework** installed (`pip install railtracks[core]`)
    - **MCP package set up** - Every MCP tool has different requirements (see specific tool documentation)
    - **Authentication credentials** - Many MCP tools require API keys or OAuth tokens

### Connecting to MCP Server Types

Railtracks supports two types of MCP servers

!!! Tip "Remote HTTP Servers"

    Use `MCPHttpParams` for connecting to remote MCP servers:

    ```python
    --8<-- "docs/scripts/MCP_tools_in_RT.py:http_example"
    ```

!!! Tip "Local Stdio Servers"

    Use `MCPStdioParams` for running local MCP servers:

    ```python
    --8<-- "docs/scripts/MCP_tools_in_RT.py:stdio_example"
    ```

### Using MCP Tools with Railtracks Agents

Once you've connected to an MCP server, you can use the tools with your Railtracks agents:

```python
--8<-- "docs/scripts/MCP_tools_in_RT.py:stdio_example"
```

### Common MCP Server Examples

??? Tip "Fetch Server (URL Content Retrieval)"
    ```python
    --8<-- "docs/scripts/MCP_tools_in_RT.py:web_search_example"
    ```
    Guide: [Websearch Server](../../../integrations/other/websearch_integration.md)

??? Tip "GitHub Server"
    

    ```python
    --8<-- "docs/scripts/MCP_tools_in_RT.py:github_example"
    ```

    Guide: [Github Server](../../../integrations/mcps/github.md)


    !!! Warning
        If you fail to provde the correct PAT you will see the following error:
        
        ```
        Exception in thread Thread-1 (_thread_main):

        Traceback (most recent call last):
        
        File "C:\Users\rc\.venv\lib\site-packages\anyio\streams\memory.py", line 111, in receive
        ```

??? Tip "Notion Server"
    
    ```python
    --8<-- "docs/scripts/MCP_tools_in_RT.py:notion_example"
    ```
    Guide: [Notion Server](../../../integrations/mcps/notion.md)
    

### Combining Multiple MCP Tools

You can combine tools from different MCP's into one single agent. 

```python
--8<-- "docs/scripts/MCP_tools_in_RT.py:multiple_mcps"
```

### Tool-Specific Guides

For detailed setup and usage instructions for specific MCP tools:

- [GitHub Tool Guide](../../../integrations/mcps/github.md)
- [Notion Tool Guide](../../../integrations/mcps//notion.md)
- [Slack Tool Guide](../../../integrations/mcps//slack.md)
- [Web Search Integration Guide](../../../integrations/other/websearch_integration.md)

## 2. Exposing Railtracks Nodes as MCP Tools


### Overview

You can expose any Railtrack Node as an MCP-compatible tool, making it accessible to any MCP client or LLM agent that supports the [Model Context Protocol (MCP)](mcp.md). This allows you to share your custom RT logic with other frameworks, agents, or applications that use MCP.

RC provides utilities to convert your Nodes into MCP tools and run a FastMCP server, so your tools are discoverable and callable via standard MCP transports (HTTP, SSE, stdio).

### Prerequisites

- **RC Framework** installed (`pip install railtracks[core]`)

### Basic Usage

#### 1. Convert RT Nodes to MCP Tools

Use the `create_mcp_server` utility to expose your RT nodes as MCP tools:

```python
--8<-- "docs/scripts/RTtoMCP.py:simple_mcp_creation"
```

This exposes your RT tool at `http://127.0.0.1:8000/mcp` for any MCP client.

#### 2. Accessing Your MCP Tools

Any MCP-compatible client or LLM agent can now discover and invoke your tool. As an example, you can use Railtracks itself to try your tool:

```python
--8<-- "docs/scripts/RTtoMCP.py:accessing_mcp"
```

## Advanced Topics

- **Multiple Tools:** Pass a list of Node classes to `create_mcp_server` to expose several tools.
- **Transport Options:** Use `streamable-http`, `sse`, or `stdio` as needed.


## Related Topics

- [What is MCP?](mcp.md)
- [Railtracks to MCP: Exposing RT Tools as MCP Tools](#2-exposing-railtracks-nodes-as-mcp-tools)

