---
description: Input and output guards attached as middleware
tags: [middleware, guardrails]
runs: 3
max_turns: 15
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Skill]
---
Using railtracks, build a customer-support agent and protect it with two guards: an input guard that blocks any user message containing an email address, and an output guard that blocks any reply containing something that looks like a credit card number. Use OpenAI.

Write everything to `main.py`, including a runnable example at the bottom. Don't run the code and don't install anything.
