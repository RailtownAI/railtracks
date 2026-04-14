# Using Notion MCP Server with RT

To use Notion tools with RT, use the `from_mcp_server` utility to load tools directly from the MCP server. For this example, ensure you have a valid Notion API token set in the environment variables. To get the token, in Notion, go to Settings > Connections > Develop or manage integrations, and create a new integration, or get the token from an existing one.

```python
--8<-- "docs/scripts/tools_mcp_guides.py:notion_mcp"
```

At this point, the tools can be used the same as any other RT tool. See the following code as a simple example.

```python
--8<-- "docs/scripts/tools_mcp_guides.py:notion_call"
```