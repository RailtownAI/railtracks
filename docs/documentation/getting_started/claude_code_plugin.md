# Claude Code Plugin

The Railtracks plugin teaches Claude Code to write Railtracks code the way it's meant to be written: agents, tools, flows, middleware, and RAG pipelines. It's the quickest way to start if you use Claude Code. It works in every project you open, even before Railtracks is installed.

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

## Plugin or `railtracks add`?

The plugin ships the same skills that `railtracks add claude:<skill>` installs. The difference is where they live and which version they follow:

- **The plugin** is installed once for you and works in every project. It follows the Railtracks `main` branch, so use it to get started or when you work across several projects.
- **`railtracks add`** writes the skills into one project's `.claude/skills/`, matched to the Railtracks version installed there. Commit them so your whole team gets the same guidance. See [AI Coding Assistants](ai_setup.md).

You don't need both. If you have both, Claude Code lists each skill twice: once as `railtracks:<skill>` from the plugin, and once as `<skill>` from your project.

## Updating

Claude Code doesn't auto-update plugins from this marketplace unless you turn that on. To pull the latest skills:

```bash
claude plugin marketplace update railtracks
claude plugin update railtracks@railtracks
```

## Other assistants

Using Codex, GitHub Copilot, or Cursor? See [AI Coding Assistants](ai_setup.md).
