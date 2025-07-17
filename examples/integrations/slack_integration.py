##################################################################
# For this example, you need to create a Slack app in your Slack
# workspace, and get the Slack team ID. You can also optionally
# specify the Slack channel IDs you want to restrict interaction to.
##################################################################
import os

from mcp import StdioServerParameters
from requestcompletion.nodes.library import from_mcp_server, tool_call_llm
import requestcompletion as rc

MCP_COMMAND = "npx"
MCP_ARGS = ["-y", "@modelcontextprotocol/server-slack"]

slack_env = {
    "SLACK_BOT_TOKEN": os.environ['SLACK_BOT_TOKEN'],
    "SLACK_TEAM_ID": os.environ['SLACK_TEAM_ID'],
    "SLACK_CHANNEL_IDS": os.environ['SLACK_CHANNEL_IDS'],
}

server = from_mcp_server(
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
    connected_nodes={*tools},
    system_message="""You are a Slack agent that can interact with Slack channels.""",
    model=rc.llm.OpenAILLM("gpt-4o"),
)

user_prompt = """Send a message to the rc-maintainer slack channel saying "Hello from your new overlord"."""
message_history = rc.llm.MessageHistory()
message_history.append(rc.llm.UserMessage(user_prompt))

with rc.Runner(rc.ExecutorConfig(logging_setting="VERBOSE")) as run:
    result = run.run_sync(agent, message_history)

print(result.answer.content)
