---
name: agent-builder
description: Build an agent using the railtracks Python framework. Use when the user wants to create an AI agent, tool-calling workflow, or multi-agent system with railtracks.
argument-hint: "[describe what the agent should do]"
---

# Build a Railtracks Agent

The user wants to build an agent using the railtracks framework: $ARGUMENTS

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
rt.llm.OpenAICompatibleProvider("my-model", api_base="https://api.example.com/v1", api_key="...")
```

---

## Steps
1. **Read the existing code** — check what files already exist in the project. Understand the task before writing anything.
2. **Identify what tools the agent needs** — each capability the agent should have becomes a `@rt.function_node`. Ask the user to clarify if it's not obvious from `$ARGUMENTS`.
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
`Parameter` fields:
- `name` — the argument name the orchestrator LLM passes
- `description` — explains what to put in this argument
- `param_type` — JSON schema type string: `"string"`, `"integer"`, `"number"`, `"boolean"`
- `required` — defaults to `True`
- `enum` — optional list of allowed values

### MCP Tools
```python
server = rt.connect_mcp(rt.MCPStdioParams(command="python", args=["-m", "my_mcp_server"]))
agent = rt.agent_node("MCP Agent", tool_nodes=server.tools, llm=llm)
```

---

## Things to Avoid
- Don't use vague docstrings — the docstring is the tool description the LLM sees.
- Don't skip type hints — they define the tool's parameter schema.
- Don't create a `Flow` and a manual `await rt.call()` for the same agent at the top level — pick one entry point.
- Don't add unnecessary tools. Only give the agent what it needs.