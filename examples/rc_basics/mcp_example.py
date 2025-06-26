#%%
import asyncio
import requestcompletion as rc
from mcp import StdioServerParameters
from requestcompletion.nodes.library.mcp_tool import async_from_mcp_server, from_mcp_server

#%%
# Install mcp_server_time for time tools:
MCP_COMMAND = "uvx"
MCP_ARGS = ["mcp-server-time"]
# Airbnb MCP server requires Node.js and the `npx` command to run.

# 
#%%
# Discover all tools
fetch_tools = from_mcp_server(StdioServerParameters(command=MCP_COMMAND, args=MCP_ARGS))

#%%
parent_tool = rc.library.tool_call_llm(
    connected_nodes={*fetch_tools},
    pretty_name="Parent Tool",
    system_message=rc.llm.SystemMessage("Provide a response using the tool when asked."),
    model=rc.llm.OpenAILLM("gpt-4o"),
)

#%%
user_message = ("What tools can you use?")

#%%
with rc.Runner(executor_config=rc.ExecutorConfig(logging_setting="QUIET", timeout=1000)) as runner:
    message_history = rc.llm.MessageHistory(
        [
            rc.llm.UserMessage(
                user_message
            )
        ]
    )
    response = asyncio.run(runner.run(parent_tool, message_history=message_history))

    print("Response:", response.answer)
