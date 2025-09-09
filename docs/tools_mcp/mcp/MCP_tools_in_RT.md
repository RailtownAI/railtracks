# Using MCP Tools in RailTracks

## Overview

!!! tip "Quick Summary"
    RailTracks makes it easy to use any MCP-compatible tool with your agents. Just connect to an MCP server, get the tools, and start using them!

RailTracks supports seamless integration with [Model Context Protocol (MCP)](mcp.md), allowing you to use any MCP-compatible tool as a native RailTracks Tool. This means you can connect your agents to a wide variety of external tools and data sources—without having to implement the tool logic yourself. 

RailTracks handles the discovery and invocation of MCP tools, so you can focus on building intelligent agents.

## Prerequisites

!!! note "Before You Begin"
    Make sure you have the following set up before using MCP tools:

- **RailTracks Framework** installed (`pip install railtracks`)
- **MCP package set up** - Every MCP tool has different requirements (see specific tool documentation)
- **Authentication credentials** - Many MCP tools require API keys or OAuth tokens

## Connecting to MCP Servers

RailTracks supports two types of MCP servers:

### 1. Remote HTTP Servers

Use `MCPHttpParams` for connecting to remote MCP servers:

```python
import os
from railtracks.nodes.library import connect_mcp
from railtracks.rt_mcp import MCPHttpParams

# Connect to a remote MCP server
fetch_server = connect_mcp(
    MCPHttpParams(
        url="https://remote.mcpservers.org/fetch/mcp",
        # Optional: Add authentication headers if needed
        headers={"Authorization": f"Bearer {os.getenv('API_KEY')}"}
    )
)
```

### 2. Local Command-Line Servers

Use `MCPStdioParams` for running local MCP servers:

```python
from railtracks.nodes.library import connect_mcp
from railtracks.rt_mcp import MCPStdioParams

# Run a local MCP server (Time server example)
time_server = connect_mcp(
    MCPStdioParams(
        command="npx",  # or other command to run the server
        args=["mcp-server-time"]
    )
)
```

## Using MCP Tools with RailTracks Agents

Once you've connected to an MCP server, you can use the tools with your RailTracks agents:

```python
import railtracks as rt
from railtracks.nodes.library import connect_mcp
from railtracks.rt_mcp import MCPHttpParams

# Connect to an MCP server (example with Fetch server)
fetch_server = connect_mcp(MCPHttpParams(url="https://remote.mcpservers.org/fetch/mcp"))
tools = fetch_server.tools  # List of RailTracks Tool Nodes

# Create an agent that can use these tools
agent = rt.library.tool_call_llm(
    tool_nodes=tools,
    name="Web Research Agent",
    system_message="Use the tools to research information online.",
    llm=rt.llm.OpenAILLM("gpt-4o"),
)

# Use the agent
with rt.Session():
    result = await rt.call(
        agent,
        "Find information about RailTracks"
    )
    print(result.content)
```

## Common MCP Server Examples

### Fetch Server (URL Content Retrieval)

```python
import railtracks as rt
from railtracks.nodes.library import connect_mcp
from railtracks.rt_mcp import MCPHttpParams

# Connect to the Fetch MCP server
fetch_server = connect_mcp(MCPHttpParams(url="https://remote.mcpservers.org/fetch/mcp"))
fetch_tools = fetch_server.tools
```

### GitHub Server

```python
import os
import railtracks as rt
from railtracks.nodes.library import connect_mcp
from railtracks.rt_mcp import MCPHttpParams

# Connect to the GitHub MCP server
github_server = connect_mcp(
    MCPHttpParams(
        url="https://api.githubcopilot.com/mcp/",
        headers={
            "Authorization": f"Bearer {os.getenv('GITHUB_PAT_TOKEN')}",
        },
    )
)
github_tools = github_server.tools
```


!!! Warning
    You must set your github token in your .env file or you will see an error like:
    
    Exception in thread Thread-1 (_thread_main):

    Traceback (most recent call last):
    
    File "C:\Users\rc\.venv\lib\site-packages\anyio\streams\memory.py", line 111, in receive

### Notion Server

```python
import json
import os
import railtracks as rt
from railtracks.nodes.library import connect_mcp
from railtracks.rt_mcp import MCPStdioParams

# Connect to the Notion MCP server
notion_server = connect_mcp(
    MCPStdioParams(
        command="npx",
        args=["-y", "@notionhq/notion-mcp-server"],
        env={
            "OPENAPI_MCP_HEADERS": json.dumps({
                "Authorization": f"Bearer {os.environ['NOTION_API_TOKEN']}",
                "Notion-Version": "2022-06-28"
            })
        },
    )
)
notion_tools = notion_server.tools
```

## Combining Multiple MCP Tools

You can combine tools from different MCP servers to create powerful agents:

```python
import railtracks as rt
from railtracks.nodes.library import connect_mcp
from railtracks.rt_mcp import MCPHttpParams, MCPStdioParams
import os
import json

# Set up servers and get tools
fetch_server = connect_mcp(MCPHttpParams(url="https://remote.mcpservers.org/fetch/mcp"))
fetch_tools = fetch_server.tools

github_server = connect_mcp(
    MCPHttpParams(
        url="https://api.githubcopilot.com/mcp/",
        headers={"Authorization": f"Bearer {os.getenv('GITHUB_PAT_TOKEN')}"},
    )
)
github_tools = github_server.tools

notion_server = connect_mcp(
    MCPStdioParams(
        command="npx",
        args=["-y", "@notionhq/notion-mcp-server"],
        env={
            "OPENAPI_MCP_HEADERS": json.dumps({
                "Authorization": f"Bearer {os.environ['NOTION_API_TOKEN']}",
                "Notion-Version": "2022-06-28"
            })
        },
    )
)
notion_tools = notion_server.tools

# Combine tools from multiple servers
all_tools = fetch_tools + github_tools + notion_tools

# Create an agent that can use all tools
super_agent = rt.library.tool_call_llm(
    tool_nodes=all_tools,
    name="Multi-Tool Agent",
    system_message="Use the appropriate tools to complete tasks.",
    llm=rt.llm.OpenAILLM("gpt-4o"),
)
```

## Tool-Specific Guides

For detailed setup and usage instructions for specific MCP tools:

- [GitHub Tool Guide](../guides/github.md)
- [Notion Tool Guide](../guides/notion.md)
- [Slack Tool Guide](../guides/slack.md)
- [Web Search Integration Guide](../guides/websearch_integration.md)

## Related Topics

- [What is MCP?](mcp.md)
- [RailTracks to MCP: Exposing RT Tools as MCP Tools](RTtoMCP.md)