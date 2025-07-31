# Notion Integration

Connect your Railtracks agents to Notion workspaces and enable them to create, read, and manage pages, databases, and content automatically.

**Version:** 0.0.1

---

## 1. What You Can Do

The Notion integration enables your Railtracks agents to:

- **Page Management**: Create, update, and organize Notion pages automatically
- **Database Operations**: Query, create, and update database entries
- **Content Creation**: Generate structured content with proper formatting
- **Workspace Organization**: Maintain and organize your Notion workspace
- **Knowledge Management**: Build automated knowledge bases and documentation systems

## 2. Quick Start

Get started with Notion integration in just a few steps:

### Step 1: Set up your Notion integration

1. Go to [Notion Integrations](https://www.notion.so/my-integrations)
2. Click "New integration" and give it a name
3. Copy the "Internal Integration Token"
4. Share your Notion pages/databases with the integration

### Step 2: Set your environment variable

```bash
export NOTION_API_TOKEN="your_notion_integration_token_here"
```

### Step 3: Create an agent with Notion capabilities

```python
import json
import os
import railtracks as rt
from mcp import StdioServerParameters
from railtracks.nodes.library.easy_usage_wrappers.mcp_tool import from_mcp_server
from railtracks.nodes.library.easy_usage_wrappers.tool_call_llm import tool_call_llm

# Set up Notion connection
MCP_COMMAND = "npx"
MCP_ARGS = ["-y", "@notionhq/notion-mcp-server"]
NOTION_VERSION = "2022-06-28"

headers = {
    "Authorization": f"Bearer {os.environ['NOTION_API_TOKEN']}",
    "Notion-Version": NOTION_VERSION
}

notion_env = {
    "OPENAPI_MCP_HEADERS": json.dumps(headers)
}

# Connect to Notion
notion_server = from_mcp_server(
    StdioServerParameters(
        command=MCP_COMMAND,
        args=MCP_ARGS,
        env=notion_env,
    )
)

# Create your agent
agent = tool_call_llm(
    connected_nodes={*notion_server.tools},
    system_message="""You are a master Notion page designer. You love creating beautiful
    and well-structured Notion pages and make sure that everything is correctly formatted.""",
    model=rt.llm.OpenAILLM("gpt-4o"),
)
```

### Step 4: Start using your agent

```python
# Create a new page with content
message_history = rt.llm.MessageHistory()
message_history.append(rt.llm.UserMessage(
    """Create a new page in Notion called 'Jokes' under the parent page "Welcome to Notion!" 
    with a small joke at the top of the page."""
))

with rt.Runner() as run:
    result = run.run_sync(agent, message_history)
    print(result.answer.content)
```

## 3. Setup Requirements

### Notion Integration Token

You'll need to create a Notion integration and get an API token:

1. **Create Integration**: Go to [Notion Integrations](https://www.notion.so/my-integrations)
2. **Get Token**: Copy the "Internal Integration Token" from your integration
3. **Share Pages**: Add your integration to any pages/databases you want it to access

### Node.js and NPX

The Notion MCP server requires Node.js to run:
- **Node.js**: Version 14 or higher
- **NPX**: Comes with Node.js (used to run the MCP server)

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `NOTION_API_TOKEN` | Yes | Your Notion integration token |

### Notion Permissions

Your integration needs to be explicitly shared with pages and databases:
- **Page Access**: Share individual pages with your integration
- **Database Access**: Share databases to allow querying and updating
- **Workspace Access**: Some operations may require workspace-level permissions

## 4. Usage Examples

### Creating Structured Content

```python
# Create a project planning page
user_prompt = """Create a new project page called 'Q1 Marketing Campaign' with:
- A project overview section
- A timeline with key milestones
- A task checklist
- A notes section for team updates"""
```

### Database Management

```python
# Add entries to a database
user_prompt = """Add a new entry to the 'Customer Feedback' database with:
- Customer: John Smith
- Rating: 5 stars
- Feedback: 'Great service and fast delivery!'
- Date: Today's date"""
```

### Content Organization

```python
# Organize existing content
user_prompt = """Review all pages under 'Meeting Notes' and create a summary page 
that lists the key decisions and action items from the last month."""
```

### Knowledge Base Creation

```python
# Build documentation
user_prompt = """Create a comprehensive FAQ page about our product return policy, 
including common questions and clear answers with proper formatting."""
```

### Getting Help

- **Examples**: Check out the complete example at `examples/integrations/notion_integration.py`
- **MCP Documentation**: Learn more about MCP tools in the [MCP integration guide](../mcp/MCP_tools_in_RT.md)
- **Notion API**: Reference the [Notion API documentation](https://developers.notion.com/) for API capabilities
