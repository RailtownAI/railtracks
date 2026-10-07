# Adding Slack integration with RT

To allow for Slack integration with RT, you need to first create a Slack app and at it to your Slack workspace - https://api.slack.com/apps. Next, get the Slack team ID (It starts with T, such as "T12345678"). You can also optionally specify the Slack channel IDs you want to restrict interaction to (ex. "C87654321, C87654322"). Finally, use the `from_mcp_server` utility to load tools directly from the MCP server.

```python
import os
from railtracks import connect_mcp, MCPStdioParams

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

SlackAgent = rt.agent_node(
    # tool_nodes={*tools},    # Uncomment this line to use the tools
    system_message="""You are a Slack agent that can interact with Slack channels.""",
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
)

user_prompt = """Send a message to general saying "Hello!"."""

slack_flow = rt.Flow("slack-flow", entry_point=SlackAgent)
result = slack_flow.invoke(user_prompt)
print(result.content)
```
