# Using MCP Tools in RailTracks

## Overview

!!! tip "Quick Summary"
    RailTracks makes it easy to use any MCP-compatible tool with your agents. Just connect to an MCP server, get the tools, and start using them!

RailTracks supports seamless integration with [Model Context Protocol (MCP)](mcp.md), allowing you to use any MCP-compatible tool as a native RailTracks Tool. This means you can connect your agents to a wide variety of external tools and data sources—without having to implement the tool logic yourself. 

RailTracks handles the discovery and invocation of MCP tools, so you can focus on building intelligent agents.

## Prerequisites

!!! note "Before You Begin"
    Make sure you have the following set up before using MCP tools:

    - **RailTracks Framework** installed (`pip install railtracks[core]`)
    - **MCP package set up** - Every MCP tool has different requirements (see specific tool documentation)
    - **Authentication credentials** - Many MCP tools require API keys or OAuth tokens

## Connecting to MCP Server Types

RailTracks supports two types of MCP servers

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

## Using MCP Tools with RailTracks Agents

Once you've connected to an MCP server, you can use the tools with your RailTracks agents:

```python
--8<-- "docs/scripts/MCP_tools_in_RT.py:stdio_example"
```

## Common MCP Server Examples

??? Tip "Fetch Server (URL Content Retrieval)"
    ```python
    --8<-- "docs/scripts/MCP_tools_in_RT.py:web_search_example"
    ```
    Guide: [Websearch Server](../guides/websearch_integration.md)

??? Tip "GitHub Server"
    

    ```python
    --8<-- "docs/scripts/MCP_tools_in_RT.py:github_example"
    ```

    Guide: [Github Server](../guides/github.md)


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
    Guide: [Notion Server](../guides/notion.md)
    

## Combining Multiple MCP Tools

You can combine tools from different MCP's into one single agent. 

```python
--8<-- "docs/scripts/MCP_tools_in_RT.py:multiple_mcps"
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