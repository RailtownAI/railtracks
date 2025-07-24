##################################################################
# For this example, ensure you have a valid GitHub PAT token set
# in the environment variables.
##################################################################
import os

from railtracks.rt_mcp import MCPHttpParams
from railtracks.nodes.library.easy_usage_wrappers.mcp_tool import from_mcp_server

from railtracks.nodes.library.easy_usage_wrappers.tool_call_llm import tool_call_llm
import railtracks as rt

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
    model=rt.llm.OpenAILLM("gpt-4o"),
)

user_prompt = """Tell me about the RailtownAI/rc repository on GitHub."""
message_history = rt.llm.MessageHistory()
message_history.append(rt.llm.UserMessage(user_prompt))

with rt.Runner() as run:
    result = run.run_sync(agent, message_history)

print(result.answer.content)
