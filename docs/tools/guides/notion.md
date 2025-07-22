# Using Notion MCP Server with RT

To use Notion tools with RT, use the `from_mcp_server` utility to load tools directly from the MCP server. For this example, ensure you have a valid Notion API token set in the environment variables. To get the token, in Notion, go to Settings > Connections > Develop or manage integrations, and create a new integration, or get the token from an existing one.

```python
import json
import os
from mcp import StdioServerParameters
from railtracks.nodes.library.easy_usage_wrappers.mcp_tool import from_mcp_server

MCP_COMMAND = "npx"
MCP_ARGS = ["-y", "@notionhq/notion-mcp-server"]
NOTION_VERSION = "2022-06-28"

headers = {
    "Authorization": f"Bearer {os.environ['NOTION_API_TOKEN']}",
    "Notion-Version": NOTION_VERSION
}

notion_env = {
    "OPENAPI_MCP_HEADERS": json.dumps(headers)
}

server = from_mcp_server(
    StdioServerParameters(
        command=MCP_COMMAND,
        args=MCP_ARGS,
        env=notion_env,
    )
)
tools = server.tools
```

At this point, the tools can be used the same as any other RT tool. See the following code as a simple example.

```python
from railtracks.nodes.library.easy_usage_wrappers.tool_call_llm import tool_call_llm
import railtracks as rt

agent = tool_call_llm(
    connected_nodes={*tools},
    system_message="""You are a master Notion page designer. You love creating beautiful
     and well-structured Notion pages and make sure that everything is correctly formatted.""",
    model=rt.llm.OpenAILLM("gpt-4o"),
)

user_prompt = """Create a new page in Notion called 'Jokes' under the parent page "Welcome to Notion!" with a small joke at the top of the page."""
message_history = rt.llm.MessageHistory()
message_history.append(rt.llm.UserMessage(user_prompt))

with rt.Runner() as run:
    result = run.run_sync(agent, message_history)

print(result.answer.content)
```