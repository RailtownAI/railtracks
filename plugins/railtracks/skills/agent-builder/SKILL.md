---
name: agent-builder
description: Build an agent using the railtracks Python framework. Use when the user wants to create an AI agent, tool-calling workflow, or multi-agent system with railtracks.
argument-hint: '[describe what the agent should do]'
---

# Build a Railtracks Agent

The user wants to build an agent using the railtracks framework: $ARGUMENTS

## How railtracks works
- **Tools** are plain Python functions decorated with `@rt.function_node`. Type hints become the parameter schema; the docstring becomes the description.
- **Agents** are created with `rt.agent_node()`. Its behaviour depends on whether tools or a structured output schema are passed (see below).
- **Flows** wrap an agent or async function as the entry point and handle execution, config, and context.
- **`rt.call()`** is used inside async workflows to call agents or nodes directly.
- **Results**: `flow.invoke()`, `await flow.ainvoke()` and `await rt.call()` on an agent return a response object. Read it with `.content`: a `str` for a text agent, an instance of your schema for an `output_schema` agent. The full conversation is on `.message_history`.

### What `agent_node` builds
`rt.agent_node()` builds one node behind the scenes — there is no separate named type to pick. What you pass changes what the agent does at runtime:

| Passed | Behaviour |
|---|---|
| Neither `tool_nodes` nor `output_schema` | Plain chat, text output |
| `output_schema` only | Structured output, no tools |
| `tool_nodes` only | Tool-calling loop, text output |

### LLM Providers

```python
# Example model IDs; use the provider and model the project already uses
rt.llm.AnthropicLLM("claude-sonnet-5-5")
rt.llm.OpenAILLM("gpt-6-luna")
rt.llm.GeminiLLM("gemini-3.8-flash")
rt.llm.OpenAICompatibleProvider(
    "my-model", api_base="https://api.example.com/v1", api_key="..."
)
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
   - `tool_nodes` listing the tools (if any), **or** `output_schema` as a Pydantic `BaseModel` for structured output — one or the other, never both (passing both raises `NodeCreationError`)
   - `llm` — follow the provider the project already uses, or one whose API key is configured (providers and their key variables: https://docs.railtracks.org/documentation/getting_started/llm_setup/); otherwise ask the user which LLM to use
   - `system_message` — a clear, specific system prompt
5. **Wrap in a Flow** — create `rt.Flow(name="...", entry_point=MyAgent)` for simple cases. For multi-step or multi-agent workflows, define an `async def` function as the entry point and use `await rt.call(MyAgent, ...)` inside it.
6. **Add invocation code** — include a `if __name__ == "__main__":` block that calls `flow.invoke(...)` with a representative example and prints `result.content`, so the user can run it immediately. Use `await flow.ainvoke(...)` instead if the code is already async.
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


llm = rt.llm.AnthropicLLM("claude-sonnet-5-5")
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
    print(result.content)
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
    llm=llm,
)
flow = rt.Flow(name="Structured Flow", entry_point=StructuredAgent)
result = flow.invoke("user query here")
print(result.content.field1)  # .content is an Output instance
```

### Multi-Agent Workflow
```python
@rt.function_node
async def pipeline(query: str) -> str:
    step1 = await rt.call(AgentA, query)
    step2 = await rt.call(AgentB, step1.content)
    return step2.content


flow = rt.Flow(name="Pipeline", entry_point=pipeline)
```

### Async Invocation
```python
import asyncio


async def main():
    result = await flow.ainvoke("user query here")
    print(result.content)


if __name__ == "__main__":
    asyncio.run(main())
```
Use `flow.invoke()` from sync code and `await flow.ainvoke()` from async code.

### Streaming
`rt.astream` streams an agent's text as it's generated. It's async only; there is no `stream=True` on models.
```python
async def main():
    stream = rt.astream(MyAgent, user_input="user query here")
    async for chunk in stream:
        print(chunk, end="", flush=True)  # str chunks
    final = stream.result  # the complete response; read final.content
```
`await rt.astream(...)` without the loop returns just the final response.

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
MCPAgent = rt.agent_node("MCP Agent", tool_nodes=server.tools, llm=llm)
```

### Visualizing Runs
Every run is recorded to `.railtracks/` automatically, no code needed. To inspect runs in the local visualizer, have the user run these from the project root:
```bash
pip install 'railtracks[visual]'
railtracks init
railtracks viz --beta
```
`railtracks viz --beta` downloads the beta UI on first use and serves it at http://localhost:3031. It blocks, so don't start it from inside the agent script.

---

## Removed or unsupported APIs — never generate these
- `agent_node(...)` without `llm=` → always pass an LLM; omitting it raises `TypeError`
- `agent_node(guardrails=...)` / `Guard(...)` → use `model_middleware=[...]` with `@rt.input_guard` / `@rt.output_guard`
- Prebuilt guards from `railtracks.guardrails.llm` (`BlockTextInputGuard`, `PIIRedactConfig`, …) → import them from `railtracks.prebuilt.guardrails`
- `stream=True` on a model (`rt.llm.OpenAILLM(..., stream=True)`) → use `rt.astream(...)`
- `rt.interactive`, `local_chat` → deprecated and being removed, no replacement
- `rt.Session()` / `@rt.session` → not part of the public API; run agents through `rt.Flow(...)`
- `result.text` / `result.structured` → read agent results with `result.content`

---

## Things to Avoid
- Don't use vague docstrings — the docstring is the tool description the LLM sees.
- Don't skip type hints — they define the tool's parameter schema.
- Don't create a `Flow` and a manual `await rt.call()` for the same agent at the top level — pick one entry point.
- Don't add unnecessary tools. Only give the agent what it needs.
