# Using GitHub MCP Server with RequestCompletion

To use the GitHub MCP server with RT, use the `from_mcp_server` utility to load tools directly from the MCP server. A valid GitHub Personal Access Token (PAT) is required, which in this example is provided via an environment variable.

```python
import os
from railtracks.integrations.rt_mcp import MCPHttpParams, connect_mcp


server = connect_mcp(
    MCPHttpParams(
        url="https://api.githubcopilot.com/mcp/",
        headers={
            "Authorization": f"Bearer {os.getenv('GITHUB_PAT_TOKEN')}",
        },
    )
)
tools = server.tools
```

At this point, the tools can be used the same as any other RT tool. See the following code as a simple example.

```python
import railtracks as rt

agent = rt.agent_node(
    tool_nodes={*tools},
    system_message="""You are a GitHub Copilot agent that can interact with GitHub repositories.""",
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
)

user_prompt = """Tell me about the RailtownAI/rc repository on GitHub."""
message_history = rt.llm.MessageHistory()
message_history.append(rt.llm.UserMessage(user_prompt))

with rt.Session():
    result = rt.call_sync(agent, message_history)

print(result.answer.content)

```
