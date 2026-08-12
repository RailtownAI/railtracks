# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

Railtracks (`rt`) is a Python framework for building agentic systems: agents, tools, and multi-step flows
defined entirely in standard Python (no YAML/DSLs). This is a `uv` workspace monorepo:

```
Root
├── packages/railtracks/          # The actual "railtracks" PyPI package
│   ├── pyproject.toml            # Package dependencies (add new deps here, in optional-dependencies for extras)
│   ├── src/railtracks/           # Source (module is railtracks, package dir uses underscore)
│   └── tests/                    # unit_tests/, integration_tests/, end_to_end/, llm_live_tests/
├── pyproject.toml                # Root workspace: dev-tooling deps only (docs/test/lint groups), NOT package deps
├── docs/                         # mkdocs documentation source
├── examples/                     # Example scripts
└── scripts/                      # CI helper scripts (dependency sorting, license checks, docs validation)
```

## Ticket Workflow

When working on a ticket/task with the user, follow this sequence:

1. **Branch first**: create a new branch dedicated to the ticket before any other work, and stay on it for
   the entire ticket unless told otherwise.
2. **Explore & understand**: read the relevant code, experiment as needed, and scope out what the ticket
   actually requires before proposing anything. For bug fixes, this step and planning (below) may merge
   into one.
3. **Plan**: once the shape of the work is clear, write the plan.
4. **Record decisions in Notion**: capture the plan and key decisions in a Notion page for this ticket
   (create one page per ticket, under the scratchpad space, via the Notion MCP) before writing any
   implementation code.
5. **Tests first**: if the ticket needs new tests, write them first and confirm they fail for the expected
   reason.
6. **Implement**: make the change, keeping existing tests and behavior intact.
7. **Commit only**: create commits when asked, but leave `git push` to the user — they push code themselves.
   They may ask for explanations along the way to stay current with what's changed.

Local, gitignored scratch docs (one pair per branch, not committed):
- `flow.md` — the running log of what changed and how it affects the codebase.
- `decisions.md` — major decisions made during the ticket, with brief rationale.

**Never publish anything externally visible** — PR creation, PR/issue comments, or any other
web-visible change — without explicit consultation first, even if a prior similar action was approved.
Each instance needs its own go-ahead unless the user has said otherwise in advance.

## Setup

```bash
uv sync --group dev
uv pip install -e "packages/railtracks[all]"   # or a specific extra, e.g. [visual], [retrieval]
```

## Common Commands

```bash
# Lint / format (must pass before commit — CI enforces this)
ruff check --fix
ruff format

# Unit tests only (fast, ~10s)
pytest packages/railtracks/tests/unit_tests/ -v --timeout=30

# Unit + integration tests (excludes llm_live_tests and retrieval e2e, per root pyproject.toml addopts)
pytest -s -v packages/railtracks/tests/unit_tests/ packages/railtracks/tests/integration_tests/

# Single test file / test
pytest packages/railtracks/tests/unit_tests/nodes/test_x.py -v
pytest packages/railtracks/tests/unit_tests/nodes/test_x.py::test_name -v

# Dependency sort check (CI enforced)
python scripts/check_dependencies_sorted.py

# Docs
mkdocs serve            # local preview at localhost:8000
mkdocs build --strict --verbose
```

CI (`.github/workflows/pr_tests.yaml`) runs, in order: `ruff check . --no-fix`, `ruff format --check .`,
license check, `check_dependencies_sorted.py`, then the full pytest suite. Run these locally before pushing.

Note: `end_to_end` and `llm_live_tests` require real API keys/network and are excluded from the default
pytest run via root `pyproject.toml` `addopts`. `RAILTRACKS_TEST_MODE` is auto-enabled during tests
(via `conftest.py`) to disable session persistence to disk; opt into persistence testing with
`RAILTRACKS_ALLOW_PERSISTENCE=1` and the `allow_persistence` fixture.

## Architecture

### Core building blocks
- **Tool**: a plain Python function wrapped via `rt.function_node`. Type hints define the parameter schema
  the LLM sees; the docstring is the tool description — both matter, don't skip either.
- **Agent**: created via `rt.agent_node(...)`, which returns a *class* (not an instance — treat it as
  PascalCase). The concrete node type is auto-selected from what's passed:

  | `tool_nodes`? | `output_schema`? | Resulting type |
  |---|---|---|
  | No | No | `TerminalLLM` |
  | No | Yes | `StructuredLLM` |
  | Yes | No | `ToolCallLLM` |
  | Yes | Yes | `StructuredToolCallLLM` |

  These live in `src/railtracks/built_nodes/concrete/`; the `rt.agent_node`/`rt.function_node` factory
  functions live in `src/railtracks/built_nodes/easy_usage_wrappers/`.
- **Flow**: `rt.Flow(name=..., entry_point=...)` wraps an agent or async function as the graph entry point
  and drives execution/config/context. `flow.invoke(...)` / `await flow.ainvoke(...)` run it.
- **`rt.call(...)`**: used *inside* an async node/tool to invoke another agent/node directly (for
  multi-agent orchestration graphs) — don't set up a second `Flow` for the same run; pick one entry point.
- **Agent-as-tool**: an `agent_node` can itself be passed in another agent's `tool_nodes`, with a
  `rt.ToolManifest(...)` describing it as a callable tool to the parent LLM.

### Package layout under `src/railtracks/`
- `nodes/` — base node abstractions (`nodes.py`, `manifest.py`, `tool_callable.py`) that everything builds on.
- `built_nodes/` — concrete node implementations (`concrete/`) and the public factory API
  (`easy_usage_wrappers/`) that produces them.
- `orchestration/` — `Flow`, the top-level execution wrapper.
- `execution/` — `coordinator.py`, `execution_strategy.py`, `task.py`: schedules and runs node graphs.
- `pubsub/` — internal publisher/subscriber messaging used to propagate execution events.
- `state/` — run state tracking (`forest.py`, `state.py`, `info.py`) — the execution graph/history model.
- `context/` — `central.py` (config/session_id), `internal.py`/`external.py` context propagation across
  async node calls.
- `llm/` — provider-agnostic LLM abstraction (`rt.llm.AnthropicLLM`, `OpenAILLM`, `GeminiLLM`,
  `OpenAICompatibleProvider`, etc., backed by litellm) plus `llm/tools/` tool-schema conversion.
- `rt_mcp/` — MCP client/server integration (`connect_mcp`, `create_mcp_server`).
- `guardrails/` — validation layers for LLM input/output and tool calls (`core/`, `llm/`, `tools/`).
- `evaluations/` — evaluators and runners for scoring agent behavior.
- `observability/` — event model, `Observer` pub/sub, and `writers/` (writer protocol) for run tracing.
- `retrieval/` — optional RAG stack: `chunking/`, `embedding/`, `loaders/`, `stores/` (install via
  `railtracks[retrieval]`).
- `human_in_the_loop/`, `prebuilt/` (ready-made tools/agents), `prompts/`, `validation/` (node
  creation/invocation checks), `utils/` (logging, serialization, visuals, config), `cli/`.
- `_session.py` — `Session`/`session()`/`ExecutionInfo`, the top-level run/session lifecycle.

### Things to avoid when writing or modifying agent code
- Don't write vague tool docstrings — it's the literal tool description the LLM sees.
- Don't omit type hints on tool functions — they define the JSON schema parameters.
- Don't create a `Flow` *and* a manual top-level `await rt.call(...)` for the same agent — one entry point.
- Don't add tools an agent doesn't need.

## Code conventions

See `.claude/skills/comment-consistency/SKILL.md` for this repo's code/comment/docstring conventions —
it's applied automatically whenever code is written or edited here.

## Notes on dependency structure
- Root `pyproject.toml` = dev tooling only (`docs`/`test`/`lint` groups via `uv`). Never add runtime
  package dependencies here.
- `packages/railtracks/pyproject.toml` = actual package dependencies. New optional integrations go under
  `[project.optional-dependencies]` there, and must stay alphabetically sorted (enforced by
  `scripts/check_dependencies_sorted.py`).
