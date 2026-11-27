# Using the Parallel Search MCP Server

[Parallel Search MCP](https://docs.parallel.ai/integrations/mcp/search-mcp) gives an agent web search and page retrieval through two tools, `web_search` and `web_fetch`. It works anonymously, so you can try it without creating an API key. The free tier has lower rate limits than an authenticated connection.

Connect with `connect_mcp` and `MCPHttpParams`, the same way as any other remote MCP server. The `User-Agent` header identifies the Railtracks version making the calls. The context manager closes the connection when the block exits.

```python
--8<-- "docs/scripts/parallel_search_mcp.py:parallel_search_mcp"
```

The script discovers the tools, runs `web_search` through a `Flow`, then runs `web_fetch` on the top result and prints the excerpts. The tools returned by `server.tools` are ordinary RT tool nodes, so they can also be passed to an agent with `tool_nodes=server.tools`.

!!! note
    Requests to the server leave your machine. Per Parallel's [Customer Terms](https://parallel.ai/customer-terms) and [Privacy Policy](https://parallel.ai/privacy-policy), queries may be retained and used for training, so avoid sending sensitive text.

To lift the free-tier limits, pass an API key in the `Authorization` header via `MCPHttpParams(headers=...)`. See the [Parallel docs](https://docs.parallel.ai/integrations/mcp/search-mcp) for the current setup.
