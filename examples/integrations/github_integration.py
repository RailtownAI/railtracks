##################################################################
# For this example, ensure you have a valid GitHub PAT token set
# in the environment variables.
##################################################################
import os

from requestcompletion.rc_mcp import MCPHttpParams
from requestcompletion.nodes.library.mcp_tool import from_mcp_server

from requestcompletion.nodes.library.easy_usage_wrappers.tool_call_llm import tool_call_llm
import requestcompletion as rc

server = from_mcp_server(
    MCPHttpParams(
        url="https://api.githubcopilot.com/mcp/",
        headers={
            "Authorization": f"Bearer {os.getenv('GITHUB_PAT_TOKEN')}",
        },
    )
)
tools = server.tools
##################################################################
# Example using the tools with an agent


agent = tool_call_llm(
    connected_nodes={*tools},
    system_message="""You are a GitHub Copilot agent that can interact with GitHub repositories.""",
    model=rc.llm.OpenAILLM("gpt-4o"),
)

user_prompt = """Tell me about the RailtownAI/rc repository on GitHub."""
message_history = rc.llm.MessageHistory()
message_history.append(rc.llm.UserMessage(user_prompt))

with rc.Runner() as run:
    result = run.run_sync(agent, message_history)

print(result.answer.content)
