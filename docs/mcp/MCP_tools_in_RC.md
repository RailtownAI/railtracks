# Using MCP Tools in RC

## Overview

RC supports seamless integration with [Model Context Protocol (MCP)](index.md), allowing you to use any MCP-compatible tool as a native RC Tool. This means you can connect your RC agents to a wide variety of external tools and data sources—without having to implement the tool logic yourself. RC handles the discovery, conversion, and invocation of MCP tools, so you can focus on building intelligent agents.

## Prerequisites

- **R C Framework** installed (`pip install R C`)
- **MCP package set up.** Every MCP tool has different requirements, so refer to the specific tool documentation for installation instructions.
- **OAuth**: Some MCP tools may require OAuth authentication. R C supports passing authorization headers into the server, but you will have to handle the OAuth flow separately.

## Basic Usage

### 1. Set up MCP Tools in R C

R C supports both remote and local MCP servers. For remote servers, you will need the server URL, and for local servers, you need the command and the args. Pass these parameters into the `MCPHttpParams` or `MCPStdioParams` classes, respectively.
To turn MCP tools into RC Tools, you can use the `from_mcp_server` function from the `requestcompletion.nodes.library` module. `from_mcp_server` returns a server object that contains all the MCP tools as RC Tool Nodes. You can get the list of tools using the `tools` property of the server object.
At this point, you can use the tools in your RC agents just like any other RC Tool!

#### Example
```python
import requestcompletion as rc
from requestcompletion.nodes.library import from_mcp_server
from requestcompletion.rc_mcp import MCPHttpParams

# Connect to an MCP server
server = from_mcp_server(MCPHttpParams(url="https://remote.mcpservers.org/fetch/mcp"))
tools = server.tools  # List of R C Tool Nodes

# Use the tools in an agent or directly
parent_tool = rc.library.tool_call_llm(
    connected_nodes=set(tools),
    pretty_name="Parent Tool",
    system_message=rc.llm.SystemMessage("Use the tool to answer questions."),
    llm_model=rc.llm.OpenAILLM("gpt-4o"),
)
```

## More Examples
- [GitHub Tool Guide](../tools/guides/github.md)
- [Notion Tool Guide](../tools/guides/notion.md)
- [Slack Tool Guide](../tools/guides/slack.md)
- [Web Search Integration Guide](../tools/guides/websearch_integration.md)

## Related Topics

- [What is MCP?](index.md)
- [RC to MCP: Exposing RC Tools as MCP Tools](RCtoMCP.md)