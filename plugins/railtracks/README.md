# Railtracks plugin for Claude Code

Teaches Claude Code to write [Railtracks](https://docs.railtracks.org/) code the way it's meant to be written: agents, tools, flows, middleware, and RAG pipelines.

## Install

```bash
claude plugin marketplace add RailtownAI/railtracks
claude plugin install railtracks@railtracks
```

## Skills

| Skill | Use it to |
|---|---|
| `agent-builder` | Build agents, tools, flows, and multi-agent workflows |
| `middleware` | Add retries, logging, guardrails, and other middleware to agents and nodes |
| `rag` | Build retrieval-augmented generation pipelines over your documents |

Each skill tells Claude to run `railtracks skill show <name>`, which prints the instructions bundled with the Railtracks version installed in your project. Upgrading Railtracks updates what Claude reads, with nothing to reinstall here. If Railtracks isn't installed yet, Claude installs it first.

## Maintaining

`skills/` is generated from `packages/railtracks/src/railtracks/cli/skills/`. Don't edit it by hand; change the bundled skill and run:

```bash
python scripts/sync_plugin_skills.py
```

CI runs it with `--check` and fails if `skills/` is out of date.
