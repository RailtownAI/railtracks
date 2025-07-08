##################################################################
# For this example, ensure you have a valid Notion API token set
# in the environment variables. To get the token, in Notion, go
# to Settings > Connections > Develop or manage integrations, and
# create a new integration, or get the token from an existing one.
##################################################################
from requestcompletion.rc_mcp import MCPHttpParams
from requestcompletion.nodes.library.mcp_tool import from_mcp_server

from requestcompletion.nodes.library.easy_usage_wrappers.tool_call_llm import tool_call_llm
import requestcompletion as rc

tools = from_mcp_server(
    MCPHttpParams(url="https://api.githubcopilot.com/mcp/")
)

##################################################################
# Example using the tools with an agent


agent = tool_call_llm(
    connected_nodes={*tools},
    system_message="""You are a GitHub Copilot agent that can interact with GitHub repositories.""",
    model=rc.llm.OpenAILLM("gpt-4o"),
)

user_prompt = """Tell me about the Pytorch repository."""
message_history = rc.llm.MessageHistory()
message_history.append(rc.llm.UserMessage(user_prompt))

with rc.Runner() as run:
    result = run.run_sync(agent, message_history)

print(result.answer.content)
