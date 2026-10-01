---
description: A basic agent with two function tools
tags: [agent-builder, core]
runs: 3
max_turns: 15
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Skill]
---
Using railtracks, build an agent that helps with cooking conversions. Give it two tools: one that converts between grams and ounces, and one that scales a recipe ingredient quantity by a number of servings. Use OpenAI. The example should ask the agent a question and print its answer.

Write everything to `main.py`, including a runnable example at the bottom. Don't run the code and don't install anything.
