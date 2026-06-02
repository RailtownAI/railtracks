# Railtracks Development Instructions

**Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.**

## Repository Overview

Railtracks is a Python framework for building agentic systems. This is a monorepo with two packages:
- `packages/railtracks/` - Core SDK with optional LLM, MCP, and integration features
- `packages/railtracks-cli/` - Command-line visualization and development tools

## Railtracks Framework Concepts

### How Railtracks Works
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
rt.llm.OpenAICompatibleProvider(base_url="...", model="...")
```

### Agent Patterns

#### Simple Agent with Tools
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

#### Structured Output
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

#### Multi-Agent Workflow
```python
@rt.function_node
async def pipeline(query: str):
    step1 = await rt.call(AgentA, query)
    step2 = await rt.call(AgentB, step1)
    return step2

flow = rt.Flow(name="Pipeline", entry_point=pipeline)
```

#### Agent as a Tool (Multi-Agent Orchestration)
```python
from railtracks.llm import Parameter

SubAgent = rt.agent_node(
    "Sub Agent",
    tool_nodes=[tool_a],
    llm=llm,
    manifest=rt.ToolManifest(
        description="Does X given a topic. Call this when you need X.",
        parameters=[
            Parameter(name="topic", description="The topic to process", param_type="string"),
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

`Parameter.param_type` may be a JSON schema type string (e.g. `"string"`) or a Python builtin (`str`, `int`, …) mapped to the same schema types.

#### MCP Tools
```python
server = rt.connect_mcp(rt.MCPStdioParams(command="python", args=["-m", "my_mcp_server"]))
agent = rt.agent_node("MCP Agent", tool_nodes=server.tools, llm=llm)
```

### Things to Avoid
- Don't use vague docstrings — the docstring is the tool description the LLM sees.
- Don't skip type hints — they define the tool's parameter schema.
- Don't create a `Flow` and a manual `await rt.call()` for the same agent at the top level — pick one entry point.
- Don't add unnecessary tools. Only give the agent what it needs.

---

## Working Effectively

### Prerequisites and Setup
- Python 3.10+ required (tested with 3.12.3)

### Development Environment Setup

**Option 1: Standard Installation** (recommended when network is reliable)
```bash
pip install -r requirements-dev.txt
```

**Option 2: Manual Installation** (for environments with network limitations)
```bash
# Install core development tools first
pip install ruff pytest pytest-asyncio pytest-cov pytest-timeout

# Install core dependencies manually (due to flit build system requirements)
pip install colorama pydantic python-dotenv litellm fastapi uvicorn watchdog mcp tomlkit

# Install documentation tools
pip install mkdocs mkdocs-material mkdocs-material-extensions mkdocs-mermaid2-plugin

# Set Python path for development (use in every session)
export PYTHONPATH=/home/runner/work/railtracks/railtracks/packages/railtracks/src:/home/runner/work/railtracks/railtracks/packages/railtracks-cli/src:$PYTHONPATH
```



### Build and Test Commands

#### Linting (FAST - runs in <1 second)
```bash
# Check code style - runs instantly
ruff check . --no-fix

# Check formatting - runs instantly  
ruff format --check .

# Fix auto-fixable issues
ruff check --fix

# Format code
ruff format
```

#### Testing (NEVER CANCEL - takes ~10 seconds)
```bash
# Run unit tests - NEVER CANCEL, completes in ~10 seconds
pytest packages/railtracks/tests/unit_tests/ -v --tb=short --timeout=30

# Run all tests including integration tests (requires OPENAI_API_KEY)
export OPENAI_API_KEY=your_key_here
pytest -s -v --junit-xml=test-results.xml --timeout=200
```

**Expected Results**: All 601+ tests should pass, ~9 second runtime. Any failures are typically due to LLM stochasticity and should be minor.

#### Documentation (NEVER CANCEL - takes ~5 seconds)
```bash
# Build documentation - NEVER CANCEL, completes in ~5 seconds  
mkdocs build --strict --verbose

# Serve documentation locally (when not in CI)
mkdocs serve
```

#### Dependency Validation
```bash
# Check dependency sorting (required for CI)
python scripts/check_dependencies_sorted.py
```

### CLI Development and Testing

#### Basic CLI Testing
```bash
# Test CLI import
python -c "import railtracks_cli; print('CLI imported successfully')"

# Show available CLI commands
python -m railtracks_cli

# Initialize railtracks (fails in limited network environments due to CDN access)
railtracks init

# Start visualizer (requires successful init first)
railtracks viz
```

**Known Issue**: CLI `init` command fails in environments with limited internet access due to CDN dependency for UI components.

### Core Functionality Validation

#### Test Basic Railtracks Operations
```bash
# Test basic function nodes
python -c "
import railtracks as rt

def multiply(a: float, b: float) -> float:
    return a * b

MultiplyNode = rt.function_node(multiply)
result = rt.call_sync(MultiplyNode, a=5.0, b=3.0)
print(f'Result: {result}')
assert result == 15.0
print('✓ Basic functionality test passed!')
"
```

#### Test Function Node Creation (from README example)
```bash
python -c "
import railtracks as rt

def number_of_chars(text: str) -> int:
    return len(text)

def number_of_words(text: str) -> int:
    return len(text.split())

TotalNumberChars = rt.function_node(number_of_chars)
TotalNumberWords = rt.function_node(number_of_words)
print('✓ Function nodes created successfully')
"
```

## Validation Scenarios

**ALWAYS run these validation steps after making code changes:**

1. **Linting validation**: `ruff check . --no-fix && ruff format --check .` (takes <1 second)
2. **Unit tests**: `pytest packages/railtracks/tests/unit_tests/ -v --timeout=30` (takes ~10 seconds)
3. **Dependency check**: `python scripts/check_dependencies_sorted.py` (takes <1 second)
4. **Basic functionality**: Run the core functionality validation scripts above
5. **Documentation build**: `mkdocs build` (takes ~5 seconds)

**NEVER SKIP** the linting validation - the CI will fail without it.

## Common Issues and Workarounds

### Installation Issues
- **Problem**: `pip install -r requirements-dev.txt` fails with network timeouts  
- **Solution**: Use manual dependency installation as shown in setup section when network connectivity is limited

### CLI Issues  
- **Problem**: `railtracks init` fails with "No address associated with hostname"
- **Explanation**: CLI requires CDN access to download UI components, fails in limited network environments
- **Workaround**: This is expected in sandboxed environments, document as known limitation

### Import Issues
- **Problem**: `ModuleNotFoundError: No module named 'railtracks'`
- **Solution**: Always set PYTHONPATH as shown in setup section for development

### Test Failures
- **Action**: All tests should pass. Focus on ensuring no new test failures are introduced. Any occasional failures are typically due to LLM stochasticity and should be minor.

## Package Structure Reference

```
railtracks/
├── packages/
│   ├── railtracks/              # Core SDK package  
│   │   ├── src/railtracks/      # Python module (underscore)
│   │   ├── tests/               # SDK tests
│   │   └── pyproject.toml       # Core package config
│   └── railtracks-cli/          # CLI package
│       ├── src/railtracks_cli/  # Python module (underscore) 
│       └── pyproject.toml       # CLI package config
├── docs/                        # Shared documentation
├── examples/                    # Code examples and demos
├── scripts/                     # Development scripts
├── requirements-dev.txt         # Development dependencies
├── mkdocs.yml                   # Documentation config
└── pyproject.toml              # Root workspace config
```

**Important**: Package names use dashes (`railtracks-cli`) but Python modules use underscores (`railtracks_cli`).

## CI Pipeline Matching

The GitHub Actions workflow runs on Windows and executes:
1. `ruff check . --no-fix` (linting)  
2. `ruff format --check .` (formatting)
3. `python scripts/check_dependencies_sorted.py` (dependency validation)
4. `pytest -s -v --junit-xml=test-results.xml --timeout=200` (full test suite)

**ALWAYS** run these same commands locally before committing to ensure CI success.

## Time Expectations and Timeouts

- **Linting**: <1 second - no timeout needed
- **Unit tests**: ~10 seconds - use 30+ second timeout
- **Full test suite**: ~3-5 minutes - use 200+ second timeout  
- **Documentation build**: ~5 seconds - use 30+ second timeout
- **Manual dependency install**: ~2-3 minutes when network is available

**NEVER CANCEL** running builds or tests - they complete quickly. Long timeouts are for safety only.