# Railtracks plugin for Claude Code

Teaches Claude Code to write [Railtracks](https://docs.railtracks.org/) code the way it's meant to be written: agents, tools, flows, middleware, and RAG pipelines.

## Install

```bash
claude plugin marketplace add RailtownAI/railtracks
claude plugin install railtracks@railtracks
```

Then start a new session or run `/reload-plugins`.

## Skills

| Skill | Use it to |
|---|---|
| `agent-builder` | Build agents, tools, flows, and multi-agent workflows |
| `middleware` | Add retries, logging, guardrails, and other middleware to agents and nodes |
| `rag` | Build retrieval-augmented generation pipelines over your documents |

These are the same skills `railtracks add claude:<skill>` installs. The plugin follows the `main` branch and works in every project, before Railtracks is installed. `railtracks add` writes the skills into one project, matched to the Railtracks version installed there, so you can commit them for your team.

## Updating

```bash
claude plugin marketplace update railtracks
claude plugin update railtracks@railtracks
```

## Maintaining

`skills/` is generated from `packages/railtracks/src/railtracks/cli/skills/`. Don't edit it by hand; change the bundled skill and run:

```bash
python scripts/sync_plugin_skills.py
```

CI runs it with `--check` and fails if `skills/` is out of date.
