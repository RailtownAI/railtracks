#%%
import railtracks as rt
from railtracks.rt_mcp import MCPHttpParams, MCPStdioParams


#%%
# NOTE: Make sure you have `mcp-server-time` installed in your environment: https://pypi.org/project/mcp-server-time/ 
# Define the command and arguments for the stdio-based MCP server
# Note: You'll need to adjust these paths for your environment
MCP_COMMAND = "python"  # Path to your executable
MCP_ARGS = ["-m", "mcp_server_time"]                      # Arguments for the executable

# 
#%%
# Discover all tools
fetch_server = rt.connect_mcp(MCPHttpParams(url="https://remote.mcpservers.org/fetch/mcp"))
time_server = rt.connect_mcp(MCPStdioParams(command=MCP_COMMAND, args=MCP_ARGS))

fetch_tools = fetch_server.tools
time_tools = time_server.tools

#%%
parent_tool = rt.agent_node(
    name="Parent Tool",
    tool_nodes={*fetch_tools, *time_tools},
    system_message=rt.llm.SystemMessage("Provide a response using the tool when asked."),
    llm=rt.llm.OpenAILLM("gpt-4o"),
)

#%%

with rt.Session(logging_setting="QUIET", timeout=1000) as runner:
    response = rt.call_sync(parent_tool, user_input="Tell me about conductr.ai. Then, tell me what time it is.")

    print("Response:", response.text)
