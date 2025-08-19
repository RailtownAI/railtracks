# Slack Integration

Connect your Railtracks agents to Slack workspaces, enabling them to send messages, read channels, and automate communication workflows.

**Version:** 0.0.1

## Table of Contents

- [1. What You Can Do](#1-what-you-can-do)
- [2. Quick Start](#2-quick-start)
- [3. Setup Requirements](#3-setup-requirements)
- [4. Usage Examples](#4-usage-examples)
- [5. Common Use Cases](#5-common-use-cases)
- [6. Troubleshooting](#6-troubleshooting)

---

## 1. What You Can Do

The Slack integration enables your Railtracks agents to:

- **Send Messages**: Post messages to public and private channels.
- **Read Channels**: Read message history from channels.
- **Automate Notifications**: Create agents that send alerts and updates from other systems.
- **Interactive Bots**: Build bots that can respond to messages and interact with users.

## 2. Quick Start

Get started with Slack integration in just a few steps:

### Step 1: Create a Slack App

1. Go to [Your Slack Apps](https://api.slack.com/apps) and click "Create New App".
2. Choose "From scratch", name your app, and select your workspace.
3. Under "Add features and functionality", click "Permissions" to go to the "OAuth & Permissions" page.
4. In the "Scopes" section, add the necessary Bot Token Scopes (e.g., `chat:write`, `channels:history`, `channels:read`).
5. Install the app to your workspace and copy the "Bot User OAuth Token".

### Step 2: Set your environment variables

```bash
export SLACK_BOT_TOKEN="xoxb-your-slack-bot-token-here"
export SLACK_TEAM_ID="T12345678"
export SLACK_CHANNEL_IDS="C12345678,C87654321"
```

### Step 3: Create an agent with Slack capabilities

```python
import os
import railtracks as rt
from mcp import StdioServerParameters
from railtracks.nodes.library import from_mcp_server, tool_call_llm

# Set up Slack connection
MCP_COMMAND = "npx"
MCP_ARGS = ["-y", "@modelcontextprotocol/server-slack"]

slack_env = {
    "SLACK_BOT_TOKEN": os.environ['SLACK_BOT_TOKEN'],
    "SLACK_TEAM_ID": os.environ['SLACK_TEAM_ID'],
    "SLACK_CHANNEL_IDS": os.environ.get('SLACK_CHANNEL_IDS', ''), # Optional
}

# Connect to Slack
slack_server = from_mcp_server(
    StdioServerParameters(
        command=MCP_COMMAND,
        args=MCP_ARGS,
        env=slack_env,
    )
)

# Create your agent
agent = tool_call_llm(
    connected_nodes={*slack_server.tools},
    system_message="You are a helpful Slack assistant.",
    model=rt.llm.OpenAILLM("gpt-4o"),
)
```

### Step 4: Start using your agent

```python
# Send a message to a channel
message_history = rt.llm.MessageHistory()
message_history.append(rt.llm.UserMessage(
    """Send a message to the 'general' channel saying 'Hello from Railtracks!'"""
))

with rt.Runner() as run:
    result = run.run_sync(agent, message_history)
    print(result.answer.content)
```

## 3. Setup Requirements

### Slack App & Bot Token

You need a Slack app with a Bot User OAuth Token. The token must have the correct permission scopes for the actions you want to perform.

- **Common Scopes**: `chat:write`, `chat:write.public`, `channels:history`, `channels:read`, `users:read`.

### Slack Team & Channel IDs

- **Team ID**: A unique identifier for your Slack workspace (starts with `T`). You can find this in the URL of your workspace (`<team-id>.slack.com`) or in your profile details.
- **Channel IDs**: (Optional) A comma-separated list of channel IDs (e.g., `C12345,C67890`) to restrict the agent's access. You can find a channel's ID in its "About" section or by copying its link.

### Node.js and NPX

The Slack MCP server requires Node.js to run.
- **Node.js**: Version 14 or higher.
- **NPX**: Comes with Node.js and is used to run the MCP server.

### Environment Variables

| Variable | Required | Description |
|---------------------|----------|----------------------------------------------------------------|
| `SLACK_BOT_TOKEN` | Yes | Your Slack app's Bot User OAuth Token (starts with `xoxb-`). |
| `SLACK_TEAM_ID` | Yes | The ID of your Slack workspace (starts with `T`). |
| `SLACK_CHANNEL_IDS` | No | Comma-separated list of channel IDs to restrict access to. |

## 4. Usage Examples

### Sending a Notification

```python
user_prompt = "Post an announcement in the #announcements channel: 'Reminder: Team meeting tomorrow at 10 AM.'"
```

### Reading Recent Messages

```python
user_prompt = "What were the last 5 messages in the #dev-team channel?"
```

### Summarizing a Channel

```python
user_prompt = "Summarize the key points from today's conversation in the #project-alpha channel."
```

### Getting Help

- **Examples**: Check out the complete example at `examples/integrations/slack_integration.py`.
- **Slack API**: Reference the [Slack API documentation](https://api.slack.com/) for more details on scopes and methods.

---