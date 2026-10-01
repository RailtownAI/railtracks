---
description: An orchestrator calling sub-agents exposed as tools
tags: [agent-builder, multi-agent]
runs: 3
max_turns: 15
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Skill]
---
Using railtracks, build a trip-planning assistant. It should be an orchestrator agent that delegates to two sub-agents it can call as tools: a weather researcher (with a stub `get_forecast(city)` tool that returns a fixed forecast) and a packing advisor that suggests what to pack given a forecast. Use OpenAI.

Write everything to `main.py`, including a runnable example at the bottom. Don't run the code and don't install anything.
