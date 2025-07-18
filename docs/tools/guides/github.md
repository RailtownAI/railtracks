# Using GitHub MCP Server with RequestCompletion

To use the GitHub MCP server with RC, use the `from_mcp_server` utility to load tools directly from the MCP server. A valid GitHub Personal Access Token (PAT) is required, which in this example is provided via an environment variable.

```python
import os
from requestcompletion.rc_mcp import MCPHttpParams
from requestcompletion.nodes.library.easy_usage_wrappers.mcp_tool import from_mcp_server

server = from_mcp_server(
    MCPHttpParams(
        url="https://api.githubcopilot.com/mcp/",
        headers={
            "Authorization": f"Bearer {os.getenv('GITHUB_PAT_TOKEN')}",
        },
    )
)
tools = server.tools
```

At this point, the tools can be used the same as any other RC tool. See the following code as a simple example.

```python
from requestcompletion.nodes.library.easy_usage_wrappers.tool_call_llm import tool_call_llm
import requestcompletion as rc

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

```
