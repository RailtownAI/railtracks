# Adding Slack integration with RT

To allow for Slack integration with RT, you need to first create a Slack app and at it to your Slack workspace - https://api.slack.com/apps. 
Next, get the Slack team ID (It starts with T, such as "T12345678"). You can also optionally specify the Slack channel IDs you want to restrict interaction to (ex. "C87654321, C87654322").
Finally, use the `from_mcp_server` utility to load tools directly from the MCP server.

```python
--8<-- "docs/scripts/tools_mcp_guides.py:slack_mcp"
```

At this point, the tools can be used the same as any other RT tool. See the following code as a simple example.

```python
--8<-- "docs/scripts/tools_mcp_guides.py:slack_call"
```