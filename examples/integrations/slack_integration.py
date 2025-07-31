##################################################################
# For this example, you need to create a Slack app in your Slack
# workspace, and get the Slack team ID. You can also optionally
# specify the Slack channel IDs you want to restrict interaction to.
##################################################################
import os

from mcp import StdioServerParameters
from railtracks.nodes.library import connect_mcp, tool_call_llm
import railtracks as rt

MCP_COMMAND = "npx"
MCP_ARGS = ["-y", "@modelcontextprotocol/server-slack"]

slack_env = {
    "SLACK_BOT_TOKEN": os.environ['SLACK_BOT_TOKEN'],
    "SLACK_TEAM_ID": os.environ['SLACK_TEAM_ID'],
    "SLACK_CHANNEL_IDS": os.environ['SLACK_CHANNEL_IDS'],
}

server = connect_mcp(
    StdioServerParameters(
        command=MCP_COMMAND,
        args=MCP_ARGS,
        env=slack_env,
    )
)
tools = server.tools

##################################################################
# Example using the tools with an agent

agent = tool_call_llm(
    tool_nodes={*tools},
    system_message="""You are a Slack agent that can interact with Slack channels.""",
    model=rt.llm.OpenAILLM("gpt-4o"),
)

user_prompt = """Send a message to thert-maintainer slack channel saying "Hello from your new overlord"."""
message_history = rt.llm.MessageHistory()
message_history.append(rt.llm.UserMessage(user_prompt))

with rt.Session(rt.ExecutorConfig(logging_setting="VERBOSE")) as run:
    result = run.run_sync(agent, message_history)

print(result.answer.content)
