---
description: A multi-step async flow using rt.call
tags: [agent-builder, async]
runs: 3
max_turns: 15
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Skill]
---
Using railtracks, build a two-step pipeline: one agent summarizes an article into three sentences, then a second agent translates that summary into French. Run the pipeline as a flow from an async `main()` function. Use OpenAI.

Write everything to `main.py`, including a runnable example at the bottom. Don't run the code and don't install anything.
