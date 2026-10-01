# Claude Code Plugin

The Railtracks plugin teaches Claude Code to write Railtracks code the way it's meant to be written: agents, tools, flows, middleware, and RAG pipelines. It's the quickest way to start if you use Claude Code, and it works before Railtracks is even installed in your project.

## Install

```bash
claude plugin marketplace add RailtownAI/railtracks
claude plugin install railtracks@railtracks
```

Start a new Claude Code session (or run `/reload-plugins`) and ask it to build something with Railtracks:

```text
Build me a railtracks agent that searches the web and summarises results
```

## What it includes

| Skill | Use it to |
|---|---|
| `agent-builder` | Build agents, tools, flows, and multi-agent workflows |
| `middleware` | Add retries, logging, guardrails, and other middleware to agents and nodes |
| `rag` | Build retrieval-augmented generation pipelines over your documents |

Claude picks the right skill on its own when your request matches it.

## How it works

Each skill tells Claude to run `railtracks skill show <name>`, which prints the instructions bundled with the Railtracks version installed in your project. So Claude always reads guidance that matches your version, and upgrading Railtracks updates what it reads, with nothing to reinstall in the plugin.

If Railtracks isn't installed yet, Claude installs it into your project first (asking you, unless you've asked it to set the project up). If the installed version is too old to have `railtracks skill show`, Claude upgrades it.

## Updating

The plugin itself changes rarely, since the instructions come from your installed Railtracks. To pull the latest version anyway:

```bash
claude plugin marketplace update railtracks
claude plugin update railtracks@railtracks
```

## Other assistants

Using Codex, GitHub Copilot, or Cursor, or prefer to commit the skills into your repository? See [AI Coding Assistants](ai_setup.md).
