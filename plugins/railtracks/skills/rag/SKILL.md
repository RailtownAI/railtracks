---
name: rag
description: Build a RAG (retrieval-augmented generation) pipeline using railtracks. Use when the user wants to ingest documents into a vector store and retrieve relevant passages to answer questions.
argument-hint: '[describe the data source and what you want to retrieve]'
---

# Build a Railtracks RAG Pipeline

The user's request: $ARGUMENTS

The instructions for this skill ship with the railtracks package, so they match the version this project has installed. Load them before writing any code:

1. Run `railtracks skill show rag` and follow what it prints.
2. If the `railtracks` command isn't found, run it with the project's Python environment, for example `uv run railtracks skill show rag`, or `python -m railtracks.cli skill show rag` with the project's virtual environment active.
3. If railtracks isn't installed, install it into the project's environment (`pip install railtracks`, or `uv add railtracks`), asking the user first if they haven't asked you to set up the project, then run the command. If it reports `Unknown command: skill`, the installed railtracks is too old: upgrade it (`pip install -U railtracks`) and run it again.
