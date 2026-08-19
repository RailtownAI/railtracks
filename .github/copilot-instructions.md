# Railtracks Development Instructions

**Always reference these instructions first and fall back to search or bash commands only when you encounter unexpected information that does not match the info here.**

## Repository Overview

Railtracks is a Python framework for building agentic systems. The repository is a `uv` workspace containing a single published package:

- `packages/railtracks/` — the SDK. Everything public is re-exported at the package root and used as `import railtracks as rt`.

The root `pyproject.toml` holds workspace config and dev tooling only (`docs`, `test`, `lint` dependency groups). Package dependencies — including every optional extra — live in `packages/railtracks/pyproject.toml`.

## Working Effectively

### Prerequisites

- Python 3.10+ (`requires-python = ">=3.10"`). CI runs 3.10.
- [`uv`](https://docs.astral.sh/uv/) for dependency management.

### Development Environment Setup

```bash
uv sync --group dev                              # docs + test + lint tooling
uv pip install -e "packages/railtracks[all]"     # SDK with all optional extras
```

The SDK is deliberately thin by default; features gate behind extras declared in `packages/railtracks/pyproject.toml` (`visual`, `retrieval`, `chroma`, `portkey`, `stores-*`, …).

**`retrieval` is not part of `[all]`.** Install it explicitly when working on the RAG stack:

```bash
uv pip install -e "packages/railtracks[all,retrieval]"
```

### Build and Test Commands

#### Linting and formatting (runs in ~1 second)

`ruff` is configured in the root `pyproject.toml`: line-length 88, target `py310`.

```bash
# What CI checks
ruff check . --no-fix
ruff format --check .

# What you run locally to fix it
ruff check --fix
ruff format
```

#### Testing (pytest, `asyncio_mode = "auto"`)

Live LLM tests (`tests/llm_live_tests`) and retrieval end-to-end tests are excluded by `addopts` in the root `pyproject.toml`, so a bare `pytest` never needs an API key.

```bash
# The core suite, matching CI
pytest -s -v \
  --ignore=packages/railtracks/tests/unit_tests/retrieval \
  packages/railtracks/tests/unit_tests/ packages/railtracks/tests/integration_tests/

# Retrieval suite (needs the retrieval extra)
pytest -s -v packages/railtracks/tests/unit_tests/retrieval/

# A single test
pytest packages/railtracks/tests/unit_tests/path/to/test_file.py::test_name
```

**Test mode:** `packages/railtracks/tests/conftest.py` auto-sets `RAILTRACKS_TEST_MODE=1`, which disables session persistence so no `.railtracks/` directory is written during a test run. A test that must verify persistence opts back in with the `allow_persistence` fixture.

#### Documentation

```bash
mkdocs build             # build the site
mkdocs serve             # preview at localhost:8000
./scripts/docs_validation.sh   # type-checks every script under docs/scripts/
```

Update `docs/` whenever you add or change a feature, and verify the render.

#### Dependency ordering

```bash
python scripts/check_dependencies_sorted.py
```

Dependencies in `packages/railtracks/pyproject.toml` must stay sorted; CI enforces this.

### CLI

The CLI ships inside the SDK at `packages/railtracks/src/railtracks/cli/`.

```bash
railtracks init          # create .railtracks/ and download the visualizer UI
railtracks update        # update the visualizer UI
railtracks viz           # start the visualizer (requires railtracks[visual])
railtracks add --list    # list the bundled coding-assistant skills
railtracks add claude:agent-builder   # install a skill for a given assistant
```

`init` and `update` download UI assets from a CDN and will fail in sandboxed environments with no network access — expected, not a bug.

## Validation Scenarios

**Always run these after making code changes:**

1. **Lint:** `ruff check . --no-fix && ruff format --check .`
2. **Core tests:** the core-suite command above
3. **Dependency order:** `python scripts/check_dependencies_sorted.py`
4. **Docs:** `mkdocs build` and `./scripts/docs_validation.sh` if you touched `docs/`
5. **Smoke test:** the snippet below

**NEVER SKIP** the lint step — CI fails without it.

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

## Common Issues and Workarounds

### `RuntimeError` from `Flow.invoke()`

`Flow.invoke()` is the synchronous entry point and cannot run inside an already-running event loop (Jupyter, FastAPI handlers, another async function). Use `await flow.ainvoke(...)` there instead.

### `ModuleNotFoundError` for an optional dependency

Heavy dependencies are gated behind extras and exposed via lazy module-level `__getattr__` imports. If an import fails, install the extra that owns it (e.g. `railtracks[retrieval]`, `railtracks[visual]`) rather than adding a top-level import.

### `railtracks init` fails with a hostname error

The CLI downloads visualizer assets from a CDN. This is expected in network-restricted environments.

### Test failures

All tests should pass. Focus on introducing no new failures; occasional flakes in LLM-touching tests come from model stochasticity.

## Repository Structure Reference

```
railtracks/
├── packages/
│   └── railtracks/              # the SDK package
│       ├── src/railtracks/      # Python module
│       ├── tests/               # unit / integration / end_to_end / llm_live_tests
│       └── pyproject.toml       # package + extras config
├── docs/                        # MkDocs documentation
├── examples/                    # code examples and demos
├── scripts/                     # development and CI scripts
├── mkdocs.yml                   # documentation config
├── pyproject.toml               # workspace + dev tooling config (not package deps)
└── uv.lock
```

## CI Pipeline Matching

`.github/workflows/pr_tests.yaml` runs on `ubuntu-latest`:

1. **Ruff lint** — `ruff check . --no-fix` and `ruff format --check .`
2. **License check** — `scripts/check_licenses.sh`
3. **Unit tests** — only when core source or tests changed
4. **Retrieval tests** — only when `retrieval/` source or tests changed
5. **Documentation validation** — `scripts/docs_validation.sh`
6. **pyproject dependency order** — `scripts/check_dependencies_sorted.py`

Steps 3 and 4 are gated on changed paths, so a docs-only PR skips the test suites.

## Conventions

- Branch naming: `feature/<issue_id>/<name>`.
- Add SDK dependencies in `packages/railtracks/pyproject.toml`, keeping each list sorted. Optional/heavy dependencies go under `optional-dependencies`.
- Keep the base import light: gate heavy dependencies behind extras with module-level `__getattr__` lazy imports plus a `TYPE_CHECKING` block, not top-level imports.
- Update `docs/` alongside any feature change.

---

## Railtracks Framework Concepts

<!--
  GENERATED — do not edit by hand.

  The section below is the bundled `agent-builder` skill
  (packages/railtracks/src/railtracks/cli/skills/agent-builder.md). Edit that file,
  then regenerate from the repository root with:

      railtracks add copilot:agent-builder --force
-->

<!-- railtracks:agent-builder:start -->
# Build a Railtracks Agent

## How railtracks works
- **Tools** are plain Python functions decorated with `@rt.function_node`. Type hints become the parameter schema; the docstring becomes the description.
- **Agents** are created with `rt.agent_node()`. The type is auto-selected based on whether tools and/or a structured output schema are provided.
- **Flows** wrap an agent or async function as the entry point and handle execution, config, and context.
- **`rt.call()`** is used inside async workflows to call agents or nodes directly.

### Agent Type Selection
| Has `tool_nodes`? | Has `output_schema`? | Agent type |
|---|---|---|
| No | No | `TerminalLLM` — plain chat |
| No | Yes | `StructuredLLM` — structured output, no tools |
| Yes | No | `ToolCallLLM` — tools, text output |
| Yes | Yes | `StructuredToolCallLLM` — tools + structured output |

### LLM Providers

```python
rt.llm.AnthropicLLM("claude-sonnet-4-6")
rt.llm.OpenAILLM("gpt-5")
rt.llm.GeminiLLM("gemini-3-flash-preview")
rt.llm.OpenAICompatibleProvider(
    "my-model", api_base="https://api.example.com/v1", api_key="..."
)
```

---

## Steps
1. **Read the existing code** — check what files already exist in the project. Understand the task before writing anything.
2. **Identify what tools the agent needs** — each capability the agent should have becomes a `@rt.function_node`. Ask the user to clarify if it's not obvious from the request.
3. **Define the tools** — write each tool as a Python function with:
   - Full type hints on all parameters and return value
   - A docstring with a one-line summary and `Args:` / `Returns:` sections
   - Real implementation (or a clear stub with a TODO if the user needs to fill it in)
4. **Define the agent** — call `rt.agent_node()` with (note: it returns a class/type, so use PascalCase for the variable name):
   - A descriptive name
   - `tool_nodes` listing the tools (if any)
   - `output_schema` as a Pydantic `BaseModel` (if structured output is needed)
   - `llm` — default to `rt.llm.AnthropicLLM("claude-sonnet-4-6")` unless the user specifies otherwise
   - `system_message` — a clear, specific system prompt
5. **Wrap in a Flow** — create `rt.Flow(name="...", entry_point=agent)` for simple cases. For multi-step or multi-agent workflows, define an `async def` function as the entry point and use `await rt.call(agent, ...)` inside it.
6. **Add invocation code** — include a `if __name__ == "__main__":` block that calls `flow.invoke(...)` with a representative example so the user can run it immediately.
7. **Check imports** — make sure `import railtracks as rt` is at the top and any Pydantic models import `from pydantic import BaseModel`.

---

## Patterns to Follow
### Simple Agent with Tools

```python
import railtracks as rt


@rt.function_node
def my_tool(param: str) -> str:
    """One-line description.
    Args:
        param: What this parameter is.
    Returns:
        What this returns.
    """
    return f"result for {param}"


llm = rt.llm.AnthropicLLM("claude-sonnet-4-6")
# agent_node returns a class (type), not an instance — use PascalCase
MyAgent = rt.agent_node(
    "Agent Name",
    tool_nodes=[my_tool],
    llm=llm,
    system_message="You are a helpful assistant that ...",
)
flow = rt.Flow(name="My Flow", entry_point=MyAgent)
if __name__ == "__main__":
    result = flow.invoke("user query here")
    print(result)
```

### Structured Output
```python
from pydantic import BaseModel


class Output(BaseModel):
    field1: str
    field2: int


StructuredAgent = rt.agent_node(
    "Structured Agent",
    output_schema=Output,
    tool_nodes=[my_tool],
    llm=llm,
)
```

### Multi-Agent Workflow
```python
@rt.function_node
async def pipeline(query: str):
    step1 = await rt.call(AgentA, query)
    step2 = await rt.call(AgentB, step1)
    return step2


flow = rt.Flow(name="Pipeline", entry_point=pipeline)
```

### Agent Used as a Tool by Another Agent (Multi-Agent Orchestration)

To expose an agent as a callable tool for another agent, pass a `rt.ToolManifest` to `agent_node`. The manifest defines how the agent appears in the tool list of its caller — its description and parameters. Without a manifest, railtracks won't know how to present the agent as a tool.
```python
from railtracks.llm import Parameter

SubAgent = rt.agent_node(
    "Sub Agent",
    tool_nodes=[tool_a],
    llm=llm,
    manifest=rt.ToolManifest(
        description="Does X given a topic. Call this when you need X.",
        parameters=[
            Parameter(
                name="topic", description="The topic to process", param_type="string"
            ),
        ],
    ),
)
Orchestrator = rt.agent_node(
    "Orchestrator",
    tool_nodes=[SubAgent],  # SubAgent is now a tool the orchestrator can call
    llm=llm,
    system_message="You are an orchestrator. Delegate to sub-agents as needed.",
)
```
`Parameter` fields:
- `name` — the argument name the orchestrator LLM passes
- `description` — explains what to put in this argument
- `param_type` — JSON schema type string (`"string"`, `"integer"`, `"number"`, `"boolean"`, …) **or** a Python builtin mapped the same way: `str`, `int`, `float` (→ `"number"`), `bool`, `list` / `tuple` / `set` (→ `"array"`), `dict` (→ `"object"`), `type(None)` (→ `"null"`). Unknown types fall back to `"object"`.
- `required` — defaults to `True`
- `enum` — optional list of allowed values

### MCP Tools
```python
server = rt.connect_mcp(
    rt.MCPStdioParams(command="python", args=["-m", "my_mcp_server"])
)
agent = rt.agent_node("MCP Agent", tool_nodes=server.tools, llm=llm)
```

---

## Things to Avoid
- Don't use vague docstrings — the docstring is the tool description the LLM sees.
- Don't skip type hints — they define the tool's parameter schema.
- Don't create a `Flow` and a manual `await rt.call()` for the same agent at the top level — pick one entry point.
- Don't add unnecessary tools. Only give the agent what it needs.
<!-- railtracks:agent-builder:end -->
