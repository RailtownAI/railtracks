---
description: Streaming an agent's output
tags: [agent-builder, streaming]
runs: 3
max_turns: 15
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Skill]
---
Using railtracks, build a storytelling agent and stream its response to the terminal as it's generated, rather than waiting for the full answer. Use OpenAI.

Write everything to `main.py`, including a runnable example at the bottom. Don't run the code and don't install anything.
