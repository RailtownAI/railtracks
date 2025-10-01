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
--8<-- "docs/scripts/tools_mcp_guides.py:websearch_imports"
```

### Step 2: Set Up MCP Tools for URL Fetching

The MCP server provides tools that can fetch and process content from URLs:

```python
--8<-- "docs/scripts/tools_mcp_guides.py:fetch_mcp_server"
```
Read more about the `from_mcp_server` utility [TODO: change this link](../mcp/mcp.md). <br>
This connects to a [remote MCP server](https://remote-mcp-servers.com/servers/ecc7629a-9f3a-487d-86fb-039f46016621) that provides URL fetching capabilities.

### Step 3: Create Custom Google Search Tool

```python
--8<-- "docs/scripts/tools_mcp_guides.py:google_search"
```

### Step 4: Create and Use the Search Agent

```python
--8<-- "docs/scripts/tools_mcp_guides.py:websearch_agent"
```

## How It Works

1. **Google Search Tool**: Uses the Google Custom Search API to find relevant web pages based on user queries
2. **MCP Fetch Tools**: Retrieves and processes content from the URLs found in search results
3. **Agent Integration**: Combines both tools to create a comprehensive web search and content analysis system
 