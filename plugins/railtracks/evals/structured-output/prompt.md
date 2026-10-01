---
description: An agent with structured output
tags: [agent-builder, core]
runs: 3
max_turns: 15
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Skill]
---
Using railtracks, build an agent that extracts contact details (full name, email address, and phone number) from a messy block of text and returns them as structured data. Use OpenAI. The example should print each extracted field.

Write everything to `main.py`, including a runnable example at the bottom. Don't run the code and don't install anything.
