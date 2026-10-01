---
description: Retrying model calls without repeating side effects
tags: [middleware, retry]
runs: 3
max_turns: 15
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Skill]
---
Using railtracks, build an agent that drafts and sends follow-up emails through a `send_email(to, subject, body)` tool (a stub that prints is fine). Make it retry when the LLM provider has a transient error, but make sure a retry can never send the same email twice. Use OpenAI.

Write everything to `main.py`, including a runnable example at the bottom. Don't run the code and don't install anything.
