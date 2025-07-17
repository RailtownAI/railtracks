-from adk
# Model Context Protocol (MCP)
## What is Model Context Protocol (MCP)?
The Model Context Protocol (MCP) is an open standard designed to standardize how Large Language Models (LLMs) like Gemini and Claude communicate with external applications, data sources, and tools. Think of it as a universal connection mechanism that simplifies how LLMs obtain context, execute actions, and interact with various systems.

## How does MCP work?
MCP follows a client-server architecture, defining how data (resources), interactive templates (prompts), and actionable functions (tools) are exposed by an MCP server and consumed by an MCP client (which could be an LLM host application or an AI agent).

## Using MCP tools in RC
RC allows you to covert MCP tools into Tools that can be used by RC agents just like any other Tool.

## RC to MCP
We also provide a way to convert RC Tools into MCP tools using FastMCP, allowing you to use your existing RC tools in any MCP-compatible environment.