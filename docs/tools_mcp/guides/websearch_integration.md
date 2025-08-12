# Web Search Integration with RequestCompletion

This guide demonstrates how to create a web search integration for RequestCompletion (RC) using both MCP (Model Context Protocol) servers and custom Google API tools. This setup allows your AI agent to search the web and fetch content from URLs.

## Prerequisites

Before implementing this integration, you'll need:

1. **Google Custom Search API credentials**:
   - Visit the [Google Cloud Console](https://console.cloud.google.com/apis/api/customsearch.googleapis.com/)
   - Enable the Custom Search API
   - Create API credentials and a Custom Search Engine ID

2. **Environment variables**: <br>
   ```
   GOOGLE_SEARCH_API_KEY=your_api_key_here
   GOOGLE_SEARCH_ENGINE_ID=your_search_engine_id_here
   ```

3. **Required packages**: <br>
   ```
   pip install railtracks python-dotenv aiohttp
   ```

## Implementation

### Step 1: Import Dependencies and Load Environment

```python
from dotenv import load_dotenv
import os
from railtracks.nodes.library import connect_mcp, tool_call_llm
import railtracks as rt
from railtracks.rt_mcp import MCPHttpParams
import aiohttp
from typing import Dict, Any

load_dotenv()
```

### Step 2: Set Up MCP Tools for URL Fetching

The MCP server provides tools that can fetch and process content from URLs:

```python
# MCP Tools that can fetch data from URLs
fetch_mcp_server = from_mcp_server(MCPHttpParams(url="https://remote.mcpservers.org/fetch/mcp"))
fetch_mcp_tools = fetch_mcp_server.tools
```
Read more about the `from_mcp_server` utility [TODO: change this link](../mcp/index.md). <br>
This connects to a [remote MCP server](https://remote-mcp-servers.com/servers/ecc7629a-9f3a-487d-86fb-039f46016621) that provides URL fetching capabilities.

### Step 3: Create Custom Google Search Tool

```python
def _format_results(data: Dict[str, Any]) -> Dict[str, Any]:
   ...


@rt.function_node
async def google_search(query: str, num_results: int = 3) -> Dict[str, Any]:
   """
   Tool for searching using Google Custom Search API
   
   Args:
       query (str): The search query
       num_results (int): The number of results to return (max 5)
   
   Returns:
       Dict[str, Any]: Formatted search results
   """
   params = {
      'key': os.environ['GOOGLE_SEARCH_API_KEY'],
      'cx': os.environ['GOOGLE_SEARCH_ENGINE_ID'],
      'q': query,
      'num': min(num_results, 5)  # Google API maximum is 5
   }

   async with aiohttp.ClientSession() as session:
      try:
         async with session.get("https://www.googleapis.com/customsearch/v1", params=params) as response:
            if response.status == 200:
               data = await response.json()
               return _format_results(data)
            else:
               error_text = await response.text()
               raise Exception(f"Google API error {response.status}: {error_text}")
      except Exception as e:
         raise Exception(f"Search failed: {str(e)}")
```

### Step 4: Create and Use the Search Agent

```python
# Combine all tools
tools = fetch_mcp_tools + [google_search]

# Create the agent with search capabilities
agent = tool_call_llm(
    connected_nodes={*tools},
    system_message="""You are an information gathering agent that can search the web.""",
    model=rt.llm.OpenAILLM("gpt-4o"),
)

# Example usage
user_prompt = """Tell me about Railtown AI."""
message_history = rt.llm.MessageHistory()
message_history.append(rt.llm.UserMessage(user_prompt))

result = rt.call_sync(agent, message_history)
print(result)
```

## How It Works

1. **Google Search Tool**: Uses the Google Custom Search API to find relevant web pages based on user queries
2. **MCP Fetch Tools**: Retrieves and processes content from the URLs found in search results
3. **Agent Integration**: Combines both tools to create a comprehensive web search and content analysis system
