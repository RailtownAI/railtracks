# Web Search Integration

Enable your Railtracks agents to search the web, fetch content from URLs, and answer questions with up-to-date information from the internet.

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

The Web Search integration combines two powerful capabilities:

- **Web Search**: Perform real-time web searches using Google's Custom Search API to find relevant information.
- **URL Fetching**: Extract and process the full content from any web page using a remote MCP server.

This allows your agents to go beyond their training data and access current information to answer questions, conduct research, and analyze online content.

## 2. Quick Start

Get started with web search in a few simple steps:

### Step 1: Get Google API Credentials

1. Go to the [Google Cloud Console](https://console.cloud.google.com/apis/api/customsearch.googleapis.com/).
2. Enable the **Custom Search API**.
3. Create an **API Key** and a **Search Engine ID**.

### Step 2: Set Environment Variables

```bash
export GOOGLE_SEARCH_API_KEY="your_api_key_here"
export GOOGLE_SEARCH_ENGINE_ID="your_search_engine_id_here"
```

### Step 3: Create an Agent with Web Search

```python
from dotenv import load_dotenv
import os
import railtracks as rt
from railtracks.rt_mcp import MCPHttpParams
from railtracks.nodes.library import from_mcp_server, tool_call_llm
import aiohttp
from typing import Dict, Any

load_dotenv()

# Tool 1: MCP server for fetching content from URLs
fetch_mcp_server = from_mcp_server(MCPHttpParams(url="https://remote.mcpservers.org/fetch/mcp"))

# Tool 2: Custom tool for Google Search
@rt.to_node
async def google_search(query: str, num_results: int = 3) -> Dict[str, Any]:
    # ... (implementation from example file) ...
    params = {
        'key': os.environ['GOOGLE_SEARCH_API_KEY'], 'cx': os.environ['GOOGLE_SEARCH_ENGINE_ID'],
        'q': query, 'num': min(num_results, 5)
    }
    async with aiohttp.ClientSession() as session:
        async with session.get("https://www.googleapis.com/customsearch/v1", params=params) as response:
            if response.status == 200: return await response.json()
            raise Exception(f"Google API error {response.status}: {await response.text()}")

# Combine tools and create the agent
tools = fetch_mcp_server.tools + [google_search]
agent = tool_call_llm(
    connected_nodes={*tools},
    system_message="You are an information gathering agent that can search the web and read URLs.",
    model=rt.llm.OpenAILLM("gpt-4o"),
)
```

### Step 4: Use the Agent

```python
# Ask the agent a question
user_prompt = "What are the latest developments in AI-powered code generation?"
message_history = rt.llm.MessageHistory()
message_history.append(rt.llm.UserMessage(user_prompt))

result = rt.call_sync(agent, message_history)
print(result.answer.content)
```

## 3. Setup Requirements

### API Credentials

- **Google API Key**: For authenticating with the Google Custom Search API.
- **Google Search Engine ID**: To specify which configured search engine to use.

### Environment Variables

| Variable | Required | Description |
|---------------------------|----------|---------------------------------|
| `GOOGLE_SEARCH_API_KEY` | Yes | Your Google Cloud API Key. |
| `GOOGLE_SEARCH_ENGINE_ID` | Yes | Your Custom Search Engine ID. |

### Python Packages

Ensure you have the necessary packages installed:
```bash
pip install railtracks python-dotenv aiohttp
```

## 4. Usage Examples

### General Research

```python
# Ask a broad question to get an overview
user_prompt = "Explain the concept of Retrieval-Augmented Generation (RAG) and its benefits."
```

### Fact-Checking

```python
# Verify a specific piece of information
user_prompt = "Who won the Nobel Prize in Physics in 2023 and for what discovery?"
```

### Product Comparison

```python
# Compare different products or technologies
user_prompt = "Compare the features and pricing of GitHub Copilot and Amazon CodeWhisperer."
```

### Getting Help

- **Examples**: See the complete working code in `examples/integrations/websearch_integration.py`.
- **MCP Documentation**: Learn more about MCP tools in the [MCP integration guide](../mcp/index.md).
- **Google API Docs**: Refer to the [Custom Search API documentation](https://developers.google.com/custom-search/v1/overview) for more details.

---