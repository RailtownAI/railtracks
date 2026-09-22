## Repository Overview

Railtracks (`rt`) is a Python framework for building agent harnesses: the loop, tools, context, controls, and record around a model, defined entirely in standard Python (no YAML/DSLs). This is a `uv` workspace monorepo:

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

## Accessing docs

Full documentation is at https://docs.railtracks.org/ and is reachable without a checkout of this repo. The source is under `docs/`, with navigation in `mkdocs.yml`. Doc URLs mirror the source path, e.g. `docs/documentation/invocation/flows.md` -> `https://docs.railtracks.org/documentation/invocation/flows/`. To verify a docs change, run `mkdocs build --strict`, which fails on broken links and nav entries.

## Setup

Python 3.10+ (`requires-python = ">=3.10"`, CI runs 3.10) and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync --group dev
uv pip install -e "packages/railtracks[all]"   # or a specific extra, e.g. [visual], [retrieval]
```

`[all]` pulls in the whole RAG stack (connectors, OCR, vector-store backends). For the retrieval pipeline without that weight, `[retrieval-core]` is the lighter opt-in (chunking, embedding, in-memory store, local loaders).

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
mkdocs serve            # blocking preview server at localhost:8000; not a verification step
mkdocs build --strict --verbose
./scripts/docs_validation.sh   # type-check the snippets under docs/scripts/
```

CI (`.github/workflows/pr_tests.yaml`) runs `ruff-lint` and `check-licenses` in parallel, plus a `changes` job that path-filters which areas were touched. `unit_tests` (includes the integration tests and an inline dependency-sort check), `retrieval_tests`, `documentation_validation` (`mkdocs build --strict`), and a standalone `pyproject_dependency_order` job all wait on those three and only run when `changes` says their area is affected. Before reporting a change as done, run `ruff check --fix`, `ruff format`, and the tests for the area you touched.

Note: `llm_live_tests` and `end_to_end/retrieval` require real API keys/network and are excluded from the default pytest run via root `pyproject.toml` `addopts`; other `end_to_end` tests run by default. `RAILTRACKS_TEST_MODE` is auto-enabled during tests (via `conftest.py`) to disable session persistence to disk; opt into persistence testing with `RAILTRACKS_ALLOW_PERSISTENCE=1` and the `allow_persistence` fixture.

## Smoke test

A fast end-to-end sanity check after a change (needs no API key):

```bash
python -c "
import railtracks as rt

def number_of_chars(text: str) -> int:
    '''Count the characters in some text.

    Args:
        text: The text to measure.
    Returns:
        The character count.
    '''
    return len(text)

CharCount = rt.function_node(number_of_chars)
flow = rt.Flow(name='Char Count', entry_point=CharCount)
assert flow.invoke('hello') == 5
print('✓ Basic functionality test passed!')
"
```

## CLI

The CLI ships inside the SDK at `packages/railtracks/src/railtracks/cli/`:

```bash
railtracks init          # create .railtracks/ and download the visualizer UI
railtracks update        # update the visualizer UI
railtracks viz           # start the visualizer server, blocking (requires railtracks[visual])
railtracks add --list    # list the bundled coding-assistant skills
railtracks add claude:agent-builder    # install a bundled skill for an assistant
```

The bundled skills `add` installs (`agent-builder`, `middleware`, `rag-pipeline`) live under `cli/skills/<name>/` as skill directories (a `SKILL.md` plus any supporting files); `add <tool>:<skill>` projects each into the assistant's native layout (Claude, Codex, Copilot, Cursor) and `<tool>:all` installs every one.

## Common issues
- **`ModuleNotFoundError` for an optional dependency** — heavy deps are gated behind extras and exposed via lazy module-level `__getattr__` imports. Install the extra that owns it (`railtracks[retrieval]`, `railtracks[visual]`, …) rather than adding a top-level import.
- **`railtracks init` or `railtracks update` fails with a hostname error** — both download visualizer assets from a CDN, so they fail without network access. This is expected, not a bug to fix.

## Architecture

### Core building blocks

For usage patterns (how to define tools/agents/flows, structured output, agent-as-tool, MCP tools), read `packages/railtracks/src/railtracks/cli/skills/agent-builder/SKILL.md` (the skill `railtracks add <tool>:agent-builder` installs for package users) or the doc linked on each entry. This list maps each concept to its source file:

- **Harness**: not a class, the assembled whole (loop + tool surface + context + controls + record). The page mapping each part to the primitive that covers it is `docs/documentation/harness/overview.md` ([Agent Harness](https://docs.railtracks.org/documentation/harness/overview/)), with runnable versions in `examples/harness/`. Use it as the framing when someone asks "how do I build an agent that does X".
- **Tool** (`rt.function_node`): `built_nodes/function/node.py`. [Function Tools](https://docs.railtracks.org/documentation/agent_design/tools/function_tools/).
- **Agent** (`rt.agent_node`): `built_nodes/llm/node.py`; always a single dynamically built node, no separate class per `tool_nodes`/`output_schema` combination. Passing both raises `NodeCreationError`. [Agent Design](https://docs.railtracks.org/documentation/agent_design/overview/).
- **Flow**: `orchestration/flow.py`. [Flows](https://docs.railtracks.org/documentation/invocation/flows/).
- **`rt.call(...)`**: `interaction/_call.py`, alongside `call_batch`/`astream`/`broadcast`/`couple`. [Call](https://docs.railtracks.org/documentation/invocation/call/).
- **Agent-as-tool**: `rt.ToolManifest(...)` in `nodes/manifest.py`. [Agents as Tools](https://docs.railtracks.org/documentation/agent_design/tools/agents_as_tools/).
- **Middleware**: `middleware/chain.py` (see "Things to avoid" below for the `middleware=`/`model_middleware=` gotcha). Use `pre_llm`/`post_llm`/`post_node` in new code; `before_llm`/`after_llm`/`after_node` are deprecated aliases kept only for compatibility. [Middleware](https://docs.railtracks.org/documentation/agent_design/middleware/overview/).
- **Human-in-the-loop verifier**: `rt.prebuilt.middleware.pre_verifier`/`post_verifier` (`prebuilt/middleware/pre_verifier.py`/`post_verifier.py`); `Verdict`/`VerifierRejectedError` are in `middleware/verdict.py`. There is no top-level `rt.verifier`; don't generate code that uses one. [Human in the Loop](https://docs.railtracks.org/observability/human_in_the_loop/hil/).

### Package layout under `src/railtracks/`
- `nodes/`: base `Node` class, `ToolManifest`, tool-callable protocol.
- `built_nodes/`: node factories, `llm/` (`agent_node`, node builder, model-call middleware) and `function/` (`function_node`, `RTFunction`).
- `orchestration/`: `Flow`, `FlowConnection`.
- `execution/`: coordinator/execution-strategy/task running the request graph.
- `interaction/`: `rt.call`, `call_batch`, `astream`, `broadcast`, `couple` (in-node calls to other nodes/agents).
- `middleware/`: generic node-level `Middleware`/`wrap_node`/`post_node` (`after_node` deprecated shim), plus `Verdict`/`VerifierRejectedError`. The human-in-the-loop gate itself is in `prebuilt/`.
- `pubsub/`: internal message bus (request creation/success/failure events).
- `state/`: execution state/forest tracking, session info.
- `context/`: `rt.context` get/put/update/delete (run-scoped context vars).
- `llm/`: model abstractions (`ModelBase`, provider clients: `AnthropicLLM`, `OpenAILLM`, `GeminiLLM`, `OpenAICompatibleProvider`, etc.), messages, tool schemas.
- `rt_mcp/`: MCP client/server integration (`connect_mcp`, `create_mcp_server`).
- `exceptions/`: the `RTError` hierarchy (`NodeCreationError`, `NodeInvocationError`, `LLMError`, `GlobalTimeOutError`, `ContextError`, `FatalError`, `VisualExtraRequiredError`).
- `guardrails/`: `input_guard`/`output_guard`, guardrail decisions/traces.
- `evaluations/`: `evaluate`, `JudgeEvaluator`, `ToolUseEvaluator`, metrics.
- `observability/`: framework-agnostic event pipeline (`Observer`, writers, `publish_event`).
- `observability_bridge/`: bridges runtime `InternalContext` scope into `observability` events.
- `events/`: internal event definitions/registry/emit plumbing (distinct from `observability`).
- `query/`: `connect`/`EventQuery` for querying recorded session/event data (DuckDB-backed).
- `retrieval/`: RAG subsystem, `RetrievalRuntime`, loaders, chunking, embedding, `Store`/`VectorStore` (install via `railtracks[retrieval]`).
- `human_in_the_loop/`: `HIL`, `HILMessage`, optional local chat UI.
- `prebuilt/`: ready-made agents/middleware/guardrails/tools, including `pre_verifier.py`/`post_verifier.py` (see above), `lock.py` (`Lock`), and `max_calls.py` (`MaxCalls`).
- `prompts/`: prompt template helpers.
- `validation/`: node-creation/invocation-time checks (duplicate tool names/params, etc.).
- `utils/`: config, logging, serialization, profiling, context-injection helpers.
- `cli/`: `railtracks` CLI (`init`/`viz`/`add`) plus bundled skill docs distributed to end users via `railtracks add claude:<skill>`, unrelated to this repo's own `.claude/skills/`. `viz_api/` is the DuckDB-backed query/route layer behind the `viz` command.
- `integrations/`: empty placeholder package; there is nothing in it to import.
- `scope_manager.py`: `ScopeManager` protocol for node/middleware scope tracking.
- `paths.py`: `resolve_railtracks_home()`, resolves the `.railtracks` data directory (env var, then walk-up-from-cwd, then a warned fallback).
- `_session.py`: `Session`/`session()` decorator.

### Things to avoid when writing or modifying agent code
- Don't create a `Flow` *and* a manual top-level `await rt.call(...)` for the same agent; pick one entry point.
- Don't add tools an agent doesn't need.
- Don't confuse `middleware=` (whole-node) with `model_middleware=` (per model-call), and don't assume middleware order is irrelevant: the first entry in the list is outermost.

## Code conventions

Follow `.claude/skills/code-style/SKILL.md` for every code change. Assistants that load skills from `.claude/skills/` may pull it in automatically based on its description, but that is not guaranteed: if it is not already in your context, read it before editing code, and check your diff against it before finishing.

## Notes on dependency structure
- Root `pyproject.toml` = dev tooling only (`docs`/`test`/`lint` groups via `uv`). Never add runtime package dependencies here.
- `packages/railtracks/pyproject.toml` = actual package dependencies. New optional integrations go under `[project.optional-dependencies]` there, and must stay alphabetically sorted (enforced by `scripts/check_dependencies_sorted.py`).
