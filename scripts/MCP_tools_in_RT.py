# --8<-- [start: http_example]
import railtracks as rt


# Connect to a remote MCP server
fetch_server = rt.connect_mcp(
    rt.MCPHttpParams(
        url="https://remote.mcpservers.org/fetch/mcp",
        # Optional: Add authentication headers if needed
        headers={"Authorization": f"Bearer {'<API_KEY>'}"},
    )
)
# --8<-- [end: http_example]

# --8<-- [start: stdio_example]
import railtracks as rt

# Run a local MCP server (Time server example)
time_server = rt.connect_mcp(
    rt.MCPStdioParams(
        command="npx",
        args=["mcp-server-time"]  # or other command to run the server
    )
)
# --8<-- [end: stdio_example]

# --8<-- [start: agent_connection]
import railtracks as rt

# Connect to an MCP server (example with Fetch server)
fetch_server = rt.connect_mcp(rt.MCPHttpParams(url="https://remote.mcpservers.org/fetch/mcp"))

# Create an agent that can use these tools
WebResearchAgent = rt.agent_node(
    tool_nodes=fetch_server.tools, # collect the tools from the MCP server
    name="Web Research Agent",
    system_message="Use the tools to research information online.",
    llm=rt.llm.OpenAILLM("gpt-4o"),
)
# --8<-- [end: agent_connection]

# --8<-- [start: web_search_example]
fetch_server = rt.connect_mcp(
    rt.MCPHttpParams(url="https://remote.mcpservers.org/fetch/mcp")
)
# --8<-- [end: web_search_example]

# --8<-- [start: github_example]
github_server = rt.connect_mcp(
    rt.MCPHttpParams(
        url="https://api.githubcopilot.com/mcp/",
        headers={
            "Authorization": f"Bearer {'<GITHUB_PAT_TOKEN>'}",
        },
    )
)
# --8<-- [end: github_example]

# --8<-- [start: notion_example]
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
# --8<-- [end: notion_example]

# --8<-- [start: multiple_mcps]
# You can combine the tools from multiple MCP servers
all_tools = notion_server.tools + github_server.tools + fetch_server.tools

# Create an agent that can use all tools
super_agent = rt.agent_node(
    tool_nodes=all_tools,
    name="Multi-Tool Agent",
    system_message="Use the appropriate tools to complete tasks.",
    llm=rt.llm.OpenAILLM("gpt-4o"),
)
# --8<-- [end: multiple_mcps]

