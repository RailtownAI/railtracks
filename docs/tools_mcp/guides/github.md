# Using GitHub MCP Server with RequestCompletion

To use the GitHub MCP server with RT, use the `from_mcp_server` utility to load tools directly from the MCP server. A valid GitHub Personal Access Token (PAT) is required, which in this example is provided via an environment variable.

```python
--8<-- "docs/scripts/tools_mcp_guides.py:github_mcp"
```

At this point, the tools can be used the same as any other RT tool. See the following code as a simple example.

```python
--8<-- "docs/scripts/tools_mcp_guides.py:github_call"
```
