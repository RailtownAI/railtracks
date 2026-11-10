# Using GitHub MCP Server with RequestCompletion

To use the GitHub MCP server with RT, use the `from_mcp_server` utility to load tools directly from the MCP server. A valid GitHub Personal Access Token (PAT) is required, which in this example is provided via an environment variable.

```python
import os
from railtracks.rt_mcp import MCPHttpParams
from railtracks import connect_mcp

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

GitHubAgent = rt.agent_node(
    # tool_nodes={*tools},    # Uncomment this line to use the tools
    system_message="""You are a GitHub Copilot agent that can interact with GitHub repositories.""",
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
)

user_prompt = """Tell me about the RailtownAI/rc repository on GitHub."""

flow = rt.Flow("github-flow", entry_point=GitHubAgent)
result = flow.invoke(user_prompt)
print(result.content)
```
