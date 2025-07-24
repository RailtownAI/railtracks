#%%
import asyncio
import railtracks as rt
from railtracks.nodes.library.easy_usage_wrappers.mcp_tool import from_mcp_server
from railtracks.rt_mcp import MCPHttpParams, MCPStdioParams


#%%
# Install mcp_server_time for time tools:
MCP_COMMAND = "uvx"
MCP_ARGS = ["mcp-server-time"]
# Airbnb MCP server requires Node.js and the `npx` command to run.

# 
#%%
# Discover all tools
fetch_server = from_mcp_server(MCPHttpParams(url="https://remote.mcpservers.org/fetch/mcp"))
time_server = from_mcp_server(MCPStdioParams(command=MCP_COMMAND, args=MCP_ARGS))

fetch_tools = fetch_server.tools
time_tools = time_server.tools

#%%
parent_tool = rt.library.tool_call_llm(
    connected_nodes={*fetch_tools, *time_tools},
    pretty_name="Parent Tool",
    system_message=rt.llm.SystemMessage("Provide a response using the tool when asked."),
    model=rt.llm.OpenAILLM("gpt-4o"),
)

#%%
user_message = ("Tell me about conductr.ai. Then, tell me what time it is.")

with rt.Runner(executor_config=rt.ExecutorConfig(logging_setting="QUIET", timeout=1000)) as runner:
    message_history = rt.llm.MessageHistory(
       [
            rt.llm.UserMessage(
                user_message
            )
        ]
    )
    response = asyncio.run(runner.run(parent_tool, user_input=message_history))

    print("Response:", response.answer)
