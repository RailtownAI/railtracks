# Model Context Protocol (MCP)

## What is Model Context Protocol (MCP)?

!!! info "MCP in a Nutshell"
    Model Context Protocol (MCP) is an open standard that enables seamless integration between Large Language Models (LLMs) and external systems, including applications, data sources, and tools.

Model Context Protocol (MCP) provides a unified interface, making it easy for LLMs to access context, perform actions, and interact with diverse environments. It standardizes how AI models communicate with external tools and services, similar to how REST APIs standardized web service communication.

### Key Benefits of MCP

- **Standardized Integration**: Connect to any MCP-compatible tool using the same interface
- **Reduced Development Time**: Use pre-built MCP tools instead of creating custom integrations
- **Ecosystem Compatibility**: Access a growing ecosystem of MCP-compatible tools and services
- **Simplified Architecture**: Uniform approach to tool integration reduces complexity


## Using MCP Tools in RailTracks

RailTracks allows you to convert MCP tools into Tools that can be used by RailTracks agents just like any other Tool. We handle the conversion and server setup for you, so you can focus on building your agents without worrying about the underlying complexities of MCP.

!!! example "Quick Example"
    ```python
    from railtracks.nodes.library import from_mcp_server
    from railtracks.rt_mcp import MCPHttpParams
    
    # Connect to a remote MCP server
    server = from_mcp_server(MCPHttpParams(url="https://remote.mcpservers.org/fetch/mcp"))
    
    # Get all available tools from the server
    tools = server.tools
    
    # Use these tools with your RailTracks agents
    ```

For a complete guide and more examples, see [Using MCP Tools in RailTracks](MCP_tools_in_RT.md).

## RailTracks to MCP

RailTracks also provides a way to convert RailTracks Tools into MCP tools using FastMCP, allowing you to use your existing RailTracks tools in any MCP-compatible environment.

This enables you to:

- Share your custom tools with the broader MCP ecosystem
- Use your tools in other MCP-compatible frameworks
- Create a unified toolset across different AI systems

See the [RailTracks to MCP](RTtoMCP.md) page for more details on how to set this up.

## Available MCP Servers

RailTracks supports pre-built integrations with various MCP servers, including:

| MCP Server    | Description | Setup Guide                                 |
|---------------|-------------|---------------------------------------------|
| **Websearch** | Retrieve and process content from URLs | [Guide](../guides/websearch_integration.md) |
| **GitHub**    | Interact with GitHub repositories | [Guide](../guides/github.md)                |
| **Notion**    | Create and manage Notion pages | [Guide](../guides/notion.md)                |
| **Slack**     | Send and receive Slack messages | [Guide](../guides/slack.md)                 |