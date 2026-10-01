---
description: A RAG pipeline over a folder of PDFs
tags: [rag]
runs: 3
max_turns: 15
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Skill]
---
Using railtracks, build a question-answering agent over a folder of PDF manuals in `./manuals`. Ingest them into a vector store that persists on disk between runs, and give an agent a tool that searches it. Use OpenAI for both embeddings and the agent.

Write everything to `main.py`, including a runnable example at the bottom. Don't run the code and don't install anything.
