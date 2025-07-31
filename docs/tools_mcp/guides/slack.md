# Adding Slack integration with RT

To allow for Slack integration with RT, you need to first create a Slack app and at it to your Slack workspace - https://api.slack.com/apps. 
Next, get the Slack team ID (It starts with T, such as "T12345678". You can also optionally specify the Slack channel IDs you want to restrict interaction to (ex. "C87654321, C87654322").
Finally, use the `from_mcp_server` utility to load tools directly from the MCP server.

```python
import os

from railtracks.integrations.rt_mcp import connect_mcp, MCPStdioParams

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
```

At this point, the tools can be used the same as any other RT tool. See the following code as a simple example.

```python

import railtracks as rt

agent = rt.agent_node(
    tool_nodes={*tools},
    system_message="""You are a Slack agent that can interact with Slack channels.""",
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
)

user_prompt = """Send a message to general saying "Hello!"."""
message_history = rt.llm.MessageHistory()
message_history.append(rt.llm.UserMessage(user_prompt))

with rt.Session(logging_setting="VERBOSE"):
    result = rt.call_sync(agent, message_history)

print(result.answer.content)
```