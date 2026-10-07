Warning

The `Model Context Protocol` was developed and adopted rapidly in late 2024/early 2025. It's seeming that the field is now focusing on tools and skills due to more efficent token context usage. Therefore this area of Railtracks is in a low maintenance state. If there are any required features needed please open an issue at [Github](https://github.com/RailtownAI/railtracks/issues)

## 1. Using MCP Tools in Railtracks

### Overview

Quick Summary

Railtracks makes it easy to use any MCP-compatible tool with your agents. Just connect to an MCP server, get the tools, and start using them!

Railtracks supports integration with [Model Context Protocol (MCP)](https://docs.railtracks.org/documentation/agent_design/tools/mcp/index.md), allowing you to use any MCP-compatible tool as a native Railtracks Tool. This means you can connect your agents to a wide variety of external tools and data sources—without having to implement the tool logic yourself.

Railtracks handles the discovery and invocation of MCP tools, so you can focus on building intelligent agents.

### Prerequisites

Before You Begin

Make sure you have the following set up before using MCP tools:

- **Railtracks Framework** installed (`pip install railtracks[core]`)
- **MCP package set up** - Every MCP tool has different requirements (see specific tool documentation)
- **Authentication credentials** - Many MCP tools require API keys or OAuth tokens

### Connecting to MCP Server Types

Railtracks supports two types of MCP servers

Remote HTTP Servers

Use `MCPHttpParams` for connecting to remote MCP servers:

```python
import railtracks as rt


# Connect to a remote MCP server
fetch_server = rt.connect_mcp(
    rt.MCPHttpParams(
        url="https://remote.mcpservers.org/fetch/mcp",
        # Optional: Add authentication headers if needed
        headers={"Authorization": f"Bearer {'<API_KEY>'}"},
    )
)
```

Local Stdio Servers

Use `MCPStdioParams` for running local MCP servers:

```python
import railtracks as rt

# Run a local MCP server (Time server example)
time_server = rt.connect_mcp(
    rt.MCPStdioParams(
        command="npx",
        args=["mcp-server-time"]  # or other command to run the server
    )
)
```

### Using MCP Tools with Railtracks Agents

Once you've connected to an MCP server, you can use the tools with your Railtracks agents:

```python
import railtracks as rt

# Run a local MCP server (Time server example)
time_server = rt.connect_mcp(
    rt.MCPStdioParams(
        command="npx",
        args=["mcp-server-time"]  # or other command to run the server
    )
)
```

### Common MCP Server Examples

Fetch Server (URL Content Retrieval)

```python
fetch_server = rt.connect_mcp(
    rt.MCPHttpParams(url="https://remote.mcpservers.org/fetch/mcp")
)
```

Guide: [Websearch Server](https://docs.railtracks.org/integrations/other/websearch_integration/index.md)

GitHub Server

```python
github_server = rt.connect_mcp(
    rt.MCPHttpParams(
        url="https://api.githubcopilot.com/mcp/",
        headers={
            "Authorization": f"Bearer {'<GITHUB_PAT_TOKEN>'}",
        },
    )
)
```

Guide: [Github Server](https://docs.railtracks.org/integrations/mcps/github/index.md)

Warning

If you fail to provde the correct PAT you will see the following error:

```text
Exception in thread Thread-1 (_thread_main):

Traceback (most recent call last):

File "C:\Users\rc\.venv\lib\site-packages\anyio\streams\memory.py", line 111, in receive
```

Notion Server

```python
import json

notion_server = rt.connect_mcp(
    rt.MCPStdioParams(
        command="npx",
        args=["-y", "@notionhq/notion-mcp-server"],
        env={
            "OPENAPI_MCP_HEADERS": json.dumps({
                "Authorization": f"Bearer {'<NOTION_API_TOKEN>'}",
                "Notion-Version": "2022-06-28"
            })
        },
    )
)
```

Guide: [Notion Server](https://docs.railtracks.org/integrations/mcps/notion/index.md)

### Combining Multiple MCP Tools

You can combine tools from different MCP's into one single agent.

```python
# You can combine the tools from multiple MCP servers
all_tools = notion_server.tools + github_server.tools + fetch_server.tools

# Create an agent that can use all tools
MultiToolAgent = rt.agent_node(
    tool_nodes=all_tools,
    name="Multi-Tool Agent",
    system_message="Use the appropriate tools to complete tasks.",
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
)
```

### Tool-Specific Guides

For detailed setup and usage instructions for specific MCP tools:

- [GitHub Tool Guide](https://docs.railtracks.org/integrations/mcps/github/index.md)
- [Notion Tool Guide](https://docs.railtracks.org/integrations/mcps/notion/index.md)
- [Slack Tool Guide](https://docs.railtracks.org/integrations/mcps/slack/index.md)
- [Web Search Integration Guide](https://docs.railtracks.org/integrations/other/websearch_integration/index.md)

## 2. Exposing Railtracks Nodes as MCP Tools

### Overview

You can expose any Railtrack Node as an MCP-compatible tool, making it accessible to any MCP client or LLM agent that supports the [Model Context Protocol (MCP)](https://docs.railtracks.org/documentation/agent_design/tools/mcp/index.md). This allows you to share your custom RT logic with other frameworks, agents, or applications that use MCP.

RC provides utilities to convert your Nodes into MCP tools and run a FastMCP server, so your tools are discoverable and callable via standard MCP transports (HTTP, SSE, stdio).

### Prerequisites

- **RC Framework** installed (`pip install railtracks[core]`)

### Basic Usage

#### 1. Convert RT Nodes to MCP Tools

Use the `create_mcp_server` utility to expose your RT nodes as MCP tools:

```python
import railtracks as rt

# Start by creating your tools
@rt.function_node
def add_nums_plus_ten(num1: int, num2: int):
    """Simple tool example."""
    return num1 + num2 + 10

# Create your MCP server with the function node
mcp = rt.create_mcp_server([add_nums_plus_ten], server_name="My MCP Server")

# Now run the MCP server
mcp.run(transport="streamable-http", host="127.0.0.1", port=8000)
```

This exposes your RT tool at `http://127.0.0.1:8000/mcp` for any MCP client.

#### 2. Accessing Your MCP Tools

Any MCP-compatible client or LLM agent can now discover and invoke your tool. As an example, you can use Railtracks itself to try your tool:

```python
server = rt.connect_mcp(rt.MCPHttpParams(url="http://127.0.0.1:8000/mcp"))
tools = server.tools
```

## Advanced Topics

- **Multiple Tools:** Pass a list of Node classes to `create_mcp_server` to expose several tools.
- **Transport Options:** Use `streamable-http`, `sse`, or `stdio` as needed.

## Related Topics

- [What is MCP?](https://docs.railtracks.org/documentation/agent_design/tools/mcp/index.md)
- [Railtracks to MCP: Exposing RT Tools as MCP Tools](#2-exposing-railtracks-nodes-as-mcp-tools)
