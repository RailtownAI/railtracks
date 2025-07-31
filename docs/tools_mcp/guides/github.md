# Using GitHub MCP Server with RequestCompletion

To use the GitHub MCP server with RT, use the `from_mcp_server` utility to load tools directly from the MCP server. A valid GitHub Personal Access Token (PAT) is required, which in this example is provided via an environment variable.

**Version:** 0.0.1

---

## 1. What You Can Do

The GitHub integration enables your Railtracks agents to:

- **Repository Analysis**: Get insights about repositories, including structure, languages, and statistics
- **Code Exploration**: Browse files, examine code, and understand project organization
- **Issue Management**: Query and interact with GitHub issues and pull requests
- **Collaborative Workflows**: Enable agents to participate in development workflows

## 2. Quick Start

Get started with GitHub integration in just a few steps:

### Step 1: Set up your GitHub token

```bash
export GITHUB_PAT_TOKEN="your_github_personal_access_token_here"
```

### Step 2: Create an agent with GitHub capabilities

```python
import os
import railtracks as rt
from railtracks.rt_mcp import MCPHttpParams
from railtracks.nodes.library.easy_usage_wrappers.mcp_tool import from_mcp_server
from railtracks.nodes.library.easy_usage_wrappers.tool_call_llm import tool_call_llm

# Connect to GitHub
github_server = from_mcp_server(
    MCPHttpParams(
        url="https://api.githubcopilot.com/mcp/",
        headers={"Authorization": f"Bearer {os.getenv('GITHUB_PAT_TOKEN')}"}
    )
)

# Create your agent
agent = tool_call_llm(
    connected_nodes={*github_server.tools},
    system_message="You are a helpful coding assistant with access to GitHub.",
    model=rt.llm.OpenAILLM("gpt-4o")
)
```

### Step 3: Start using your agent

```python
# Ask your agent about a repository
message_history = rt.llm.MessageHistory()
message_history.append(rt.llm.UserMessage(
    "Can you tell me about the structure of the microsoft/vscode repository?"
))

with rt.Runner() as run:
    result = run.run_sync(agent, message_history)
    print(result.answer.content)
```

## 3. Setup Requirements

### GitHub Personal Access Token

You'll need a GitHub Personal Access Token (PAT) with appropriate permissions:

1. Go to [GitHub Settings > Developer settings > Personal access tokens](https://github.com/settings/tokens)
2. Click "Generate new token (classic)"
3. Select the permissions your agent needs:
   - `repo` - For private repository access
   - `public_repo` - For public repository access
   - `read:org` - For organization information

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_PAT_TOKEN` | Yes | Your GitHub Personal Access Token |

## 4. Usage Examples

### Repository Information

```python
# Get repository overview
user_prompt = "What programming languages are used in the tensorflow/tensorflow repository?"
```

### Code Analysis

```python
# Analyze specific files or directories
user_prompt = "Can you explain the main function in the src/main.py file of the user/project repository?"
```

### Issue and PR Management

```python
# Query issues and pull requests
user_prompt = "Show me the open issues labeled 'bug' in the rails/rails repository"
```

### Project Planning

```python
# Help with project planning
user_prompt = "Based on the project structure of facebook/react, suggest how I should organize my new React component library"
```
