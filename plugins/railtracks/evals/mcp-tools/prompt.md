---
description: An agent using MCP server tools
tags: [agent-builder, mcp]
runs: 3
max_turns: 15
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Skill]
---
Using railtracks, build an agent that can fetch a web page and summarize it, using the tools from the MCP fetch server, which runs over stdio with the command `uvx mcp-server-fetch`. Use OpenAI.

Write everything to `main.py`, including a runnable example at the bottom. Don't run the code and don't install anything.
