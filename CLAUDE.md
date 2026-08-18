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

## Setup

```bash
uv sync --group dev
uv pip install -e "packages/railtracks[all]"   # or a specific extra, e.g. [visual], [retrieval]
```

## Common Commands

```bash
# Lint / format (must pass before commit, CI enforces this)
ruff check --fix
ruff format

# Unit tests only (fast, ~10s)
pytest packages/railtracks/tests/unit_tests/ -v --timeout=30

# Unit + integration tests (excludes llm_live_tests and end_to_end/retrieval, per root pyproject.toml addopts)
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

Note: `llm_live_tests` and `end_to_end/retrieval` require real API keys/network and are excluded from the
default pytest run via root `pyproject.toml` `addopts`; other `end_to_end` tests run by default.
`RAILTRACKS_TEST_MODE` is auto-enabled during tests (via `conftest.py`) to disable session persistence to
disk; opt into persistence testing with `RAILTRACKS_ALLOW_PERSISTENCE=1` and the `allow_persistence`
fixture.

## Architecture

### Core building blocks

For usage patterns (how to define tools/agents/flows, structured output, agent-as-tool, MCP tools), see
`packages/railtracks/src/railtracks/cli/skills/agent-builder.md` (the same content bundled for package
users via `railtracks add claude:agent-builder`); don't re-teach usage here. This section is just where
things live internally and dev-relevant gotchas that skill doesn't cover:

- **Tool** (`rt.function_node`): `built_nodes/function/node.py`.
- **Agent** (`rt.agent_node`): `built_nodes/llm/node.py`, returns a *class* (not an instance, treat it as
  PascalCase); built via `LLMNodeBuilder.llm(...)` (`built_nodes/llm/node_builder.py`). There's no separate
  named class per `tool_nodes`/`output_schema` combination; it's always a single dynamically built node.
- **Flow**: `orchestration/flow.py`. `flow.invoke(...)` / `await flow.ainvoke(...)` run it.
- **`rt.call(...)`**: moved to `interaction/` (`interaction/_call.py`) as of the 1.5 merge, alongside
  `call_batch`, `astream`, `broadcast`, `couple`. Don't set up a second `Flow` for the same run; pick one
  entry point.
- **Agent-as-tool**: `rt.ToolManifest(...)` lives in `nodes/manifest.py`.
- **Middleware**: `agent_node(middleware=[...])` wraps the whole node boundary (`user_input -> Response`);
  `agent_node(model_middleware=[...])` wraps each raw model call inside the tool-calling loop; using the
  wrong one silently misses tool-call retries or wraps too broadly. `MiddlewareChain.run`
  (`middleware/chain.py`) composes via `reversed(list)`: the first entry in `middleware=[...]` is
  outermost, the last is innermost/closest to the actual call.
- **Human-in-the-loop verifier**: `rt.verifier(approve_fn, *, timeout=, name=)` (`middleware/verifier.py`)
  is a `wrap_node` middleware that gates a node's execution on an approve/reject callback (sync or async),
  returning a `Verdict` (`middleware/verdict.py`) or raising `VerifierRejectedError` on rejection/timeout.

### Package layout under `src/railtracks/`
- `nodes/`: base `Node` class, `ToolManifest`, tool-callable protocol.
- `built_nodes/`: node factories, `llm/` (`agent_node`, node builder, model-call middleware) and
  `function/` (`function_node`, `RTFunction`).
- `orchestration/`: `Flow`, `FlowConnection`.
- `execution/`: coordinator/execution-strategy/task running the request graph.
- `interaction/`: `rt.call`, `call_batch`, `astream`, `broadcast`, `couple` (in-node calls to other
  nodes/agents).
- `middleware/`: generic node-level `Middleware`/`wrap_node`/`after_node` (wraps whole node invocation),
  plus the `verifier`/`Verdict`/`VerifierRejectedError` human-in-the-loop gate.
- `pubsub/`: internal message bus (request creation/success/failure events).
- `state/`: execution state/forest tracking, session info.
- `context/`: `rt.context` get/put/update/delete (run-scoped context vars).
- `llm/`: model abstractions (`ModelBase`, provider clients: `AnthropicLLM`, `OpenAILLM`, `GeminiLLM`,
  `OpenAICompatibleProvider`, etc.), messages, tool schemas.
- `rt_mcp/`: MCP client/server integration (`connect_mcp`, `create_mcp_server`).
- `exceptions/`: the `RTError` hierarchy (`NodeCreationError`, `NodeInvocationError`, `LLMError`,
  `GlobalTimeOutError`, `ContextError`, `FatalError`, `VisualExtraRequiredError`).
- `guardrails/`: `input_guard`/`output_guard`, guardrail decisions/traces.
- `evaluations/`: `evaluate`, `JudgeEvaluator`, `ToolUseEvaluator`, metrics.
- `observability/`: framework-agnostic event pipeline (`Observer`, writers, `publish_event`).
- `observability_bridge/`: bridges runtime `InternalContext` scope into `observability` events.
- `events/`: internal event definitions/registry/emit plumbing (distinct from `observability`).
- `query/`: `connect`/`EventQuery` for querying recorded session/event data (DuckDB-backed).
- `retrieval/`: RAG subsystem, `RetrievalRuntime`, loaders, chunking, embedding, `Store`/`VectorStore`
  (install via `railtracks[retrieval]`).
- `human_in_the_loop/`: `HIL`, `HILMessage`, optional local chat UI.
- `prebuilt/`: ready-made agents/middleware/guardrails/tools.
- `prompts/`: prompt template helpers.
- `validation/`: node-creation/invocation-time checks (duplicate tool names/params, etc.).
- `utils/`: config, logging, serialization, profiling, prompt-injection helpers.
- `cli/`: `railtracks` CLI (`init`/`viz`/`add`) plus bundled skill docs distributed to end users via
  `railtracks add claude:<skill>`, unrelated to this repo's own `.claude/skills/`.
- `integrations/`: currently an empty placeholder package, no functionality yet.
- `scope_manager.py`: `ScopeManager` protocol for node/middleware scope tracking.
- `paths.py`: `resolve_railtracks_home()`, resolves the `.railtracks` data directory (env var, then
  walk-up-from-cwd, then a warned fallback).
- `_session.py`: `Session`/`session()` decorator.

### Things to avoid when writing or modifying agent code
- Don't write vague tool docstrings: it's the literal tool description the LLM sees.
- Don't omit type hints on tool functions: they define the JSON schema parameters.
- Don't create a `Flow` *and* a manual top-level `await rt.call(...)` for the same agent; pick one entry
  point.
- Don't add tools an agent doesn't need.
- Don't confuse `middleware=` (whole-node) with `model_middleware=` (per model-call), and don't assume
  middleware order is irrelevant: the first entry in the list is outermost.

## Code conventions

See `.claude/skills/code-style/SKILL.md` for this repo's code-style conventions. It's a
project-scoped Claude Code skill: Claude auto-invokes it based on its description whenever it's writing or
editing code here, which is a model-driven nudge from the skill matching, not a hard-enforced hook, so
still sanity-check the diff against it yourself.

## Notes on dependency structure
- Root `pyproject.toml` = dev tooling only (`docs`/`test`/`lint` groups via `uv`). Never add runtime
  package dependencies here.
- `packages/railtracks/pyproject.toml` = actual package dependencies. New optional integrations go under
  `[project.optional-dependencies]` there, and must stay alphabetically sorted (enforced by
  `scripts/check_dependencies_sorted.py`).
