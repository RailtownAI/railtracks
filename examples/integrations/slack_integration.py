##################################################################
# For this example, you need to create a Slack app in your Slack
# workspace, and get the Slack team ID. You can also optionally
# specify the Slack channel IDs you want to restrict interaction to.
##################################################################
import os


from railtracks import connect_mcp, MCPStdioParams
import railtracks as rt
import asyncio

MCP_COMMAND = "npx"
MCP_ARGS = ["-y", "@modelcontextprotocol/server-slack"]

slack_env = {
    "SLACK_BOT_TOKEN": os.environ['SLACK_BOT_TOKEN'],
    "SLACK_TEAM_ID": os.environ['SLACK_TEAM_ID'],
    "SLACK_CHANNEL_IDS": os.environ['SLACK_CHANNEL_IDS'],
}

server = connect_mcp(
    MCPStdioParams(
        command=MCP_COMMAND,
        args=MCP_ARGS,
        env=slack_env,
    )
)
tools = server.tools

##################################################################
# Example using the tools with an agent

agent = rt.agent_node(
    tool_nodes={*tools},
    system_message="""You are a Slack agent that can interact with Slack channels.""",
    llm=rt.llm.OpenAILLM("gpt-4o"),
)

user_prompt = """Send a message to thert-maintainer slack channel saying "Hello from your new overlord"."""
message_history = rt.llm.MessageHistory()
message_history.append(rt.llm.UserMessage(user_prompt))

async def call_node():
    with rt.Session(logging_setting="VERBOSE"):
        result = await rt.call(agent, message_history)

    print(result.content)

asyncio.run(call_node())
