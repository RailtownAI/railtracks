##################################################################
# For this example, ensure you have a valid Notion API token set
# in the environment variables. To get the token, in Notion, go
# to Settings > Connections > Develop or manage integrations, and
# create a new integration, or get the token from an existing one.
##################################################################
import json
import os

from mcp import StdioServerParameters
from railtracks.nodes.library.easy_usage_wrappers.mcp_tool import connect_mcp

from railtracks.nodes.library.easy_usage_wrappers.tool_calling_llms.tool_call_llm import tool_call_llm
import railtracks as rt


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

server = connect_mcp(
    StdioServerParameters(
        command=MCP_COMMAND,
        args=MCP_ARGS,
        env=notion_env,
    )
)
tools = server.tools

##################################################################
# Example using the tools with an agent


agent = tool_call_llm(
    tool_nodes={*tools},
    system_message="""You are a master Notion page designer. You love creating beautiful
     and well-structured Notion pages and make sure that everything is correctly formatted.""",
    model=rt.llm.OpenAILLM("gpt-4o"),
)

user_prompt = """Create a new page in Notion called 'Jokes' under the parent page "Welcome to Notion!" with a small joke at the top of the page."""
message_history = rt.llm.MessageHistory()
message_history.append(rt.llm.UserMessage(user_prompt))

with rt.Session() as run:
    result = run.run_sync(agent, message_history)

print(result.answer.content)
