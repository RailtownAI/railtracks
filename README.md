# Railtracks

<p align="center">
  <img alt="Railtracks" src="https://railtracksstorage.blob.core.windows.net/railtrackswebsite/images/logo.svg" width="40%">
</p>
<br>

<p align="center">
  <a href="https://pypi.org/project/railtracks/">
    <img src="https://img.shields.io/pypi/v/railtracks?color=brightgreen&style=for-the-badge" alt="PyPI Version" />
  </a>
  <a href="https://pypi.org/project/railtracks/">
    <img src="https://img.shields.io/pypi/pyversions/railtracks?style=for-the-badge&logo=python&logoColor=white" alt="Python Versions" />
  </a>
  <a href="https://pypistats.org/packages/railtracks">
    <img src="https://img.shields.io/pypi/dm/railtracks?style=for-the-badge&color=blue" alt="Monthly Downloads" />
  </a>
  <a href="https://opensource.org/licenses/MIT">
    <img src="https://img.shields.io/pypi/l/railtracks?style=for-the-badge&color=lightgrey" alt="License" />
  </a>
  <a href="https://github.com/RailtownAI/railtracks/stargazers">
    <img src="https://img.shields.io/github/stars/RailtownAI/railtracks?style=for-the-badge&logo=github" alt="GitHub Stars" />
  </a>
</p>

<p align="center">
  <b>Own the AI!</b><br>
  Assemble a custom agent harness in plain Python. The loop, the tools, the context, the controls, the record. All yours.
</p>

## What is Railtracks?

Railtracks is a Python **agent framework** for building your own **harness**. Every piece is an ordinary Python object you assemble yourself: a tool-calling loop, a tool surface of functions, sub-agents and MCP servers, context management, permission and budget controls, and a replayable record of every run. No YAML, no DSL, no black-box runtime.


```python
import railtracks as rt


# Define a tool (just a function!)
def get_weather(location: str) -> str:
    """Get the current weather for a location."""
    return f"It's sunny in {location}!"


# Create an agent with tools
agent = rt.agent_node(
    "Weather Assistant",
    # Alternatively, use @rt.function_node at def time
    tool_nodes=[rt.function_node(get_weather)],
    llm=rt.llm.OpenAILLM("gpt-5.4-mini"),
    system_message="You help users with weather information.",
)

# Run it
flow = rt.Flow(name="Weather Flow", entry_point=agent)
result = flow.invoke("What's the weather in Paris?")
# or `await flow.ainvoke("What's the weather in Paris?")` in an async context
print(result.text)  # "Based on the current data, it's sunny in Paris!"
```

Execution order, branching, and looping are expressed using standard Python control flow.

## What is an agent harness?

Everything around the model call. The model brings judgment. The harness brings the loop that keeps calling it, the tools it can reach, what lands in its context, the limits on what it may do, and the record of what it did. Change your model tomorrow and the harness is what you still own.

Five parts. Take the ones your problem needs, wire them together in plain Python, leave the rest out.

| Part | What it decides | Railtracks primitives |
|---|---|---|
| **Loop** | When the agent keeps going, and when it's done | `rt.agent_node` runs the tool-calling loop; `rt.Flow` and `rt.call` drive multi-step work |
| **Tool surface** | What the agent can actually do | `rt.function_node`, `rt.ToolManifest` for agents-as-tools, `rt.connect_mcp` for MCP servers |
| **Context** | What the model sees on this turn | `system_message`, `rt.context`, todo and key-value memory toolsets, retrieval |
| **Controls** | What it's allowed to do, and how much of it | `MaxCalls`, `Timeout`, `Retry`, `Lock`, human-in-the-loop verifiers, guardrails |
| **Record** | What happened, and whether you can replay it | Session state, `railtracks viz`, `rt.evaluate` |

The shapes this usually takes:

- **Coding harness.** Read, edit, and shell tools, a todo list that survives across turns, human approval on anything that touches the working tree. Runnable in [`examples/harness/coding_harness.py`](examples/harness/coding_harness.py).
- **Research harness.** Search and fetch, retrieval over what it has gathered, memory for findings, a structured-output pass to force the report into a schema.
- **Operations harness.** A few high-consequence tools, each behind a real approver, with an audit trail you can hand to someone else.

Start with the [Agent Harness guide](https://docs.railtracks.org/documentation/harness/overview/), or run the [harness examples](examples/harness) as they are: a read-only harness in under 80 lines, and a coding harness whose file writes and shell commands each stop for your approval.

## Why Railtracks?

<div align="center">

<table>
<tr>
<td width="50%" valign="top">

#### Pure Python
```python
# Write agents like regular functions
@rt.function_node
def my_tool(text: str) -> str:
    return process(text)
```
- No YAML, no DSLs, no magic strings
- Compatible with standard debuggers
- Full IDE autocomplete and type checking

</td>
<td width="50%" valign="top">

#### Tool-First Architecture
```python
# Any function becomes a tool
agent = rt.agent_node("Assistant", tool_nodes=[my_tool, api_call])
```
- Automatic function-to-tool conversion
- Seamless API and database integration
- MCP protocol support

</td>
</tr>
<tr>
<td width="50%" valign="top">

#### Familiar Interface
```python
# Native Async support
result = await rt.call(agent, query)
```
- Standardized `call` interface, consistent with asyncio patterns
- Built-in validation, error handling, and retries
- Automatic parallelization management

</td>
<td width="50%" valign="top">

#### Built-in Observability

Railtracks includes a visualizer for inspecting agent runs and evaluations in real-time, run completely locally with no signups required.

See the [Observability documentation](https://docs.railtracks.org/observability/agenthub/local/) for setup and usage.

</td>
</tr>
</table>

</div>

## Quick Start

<details open>
<summary><b>Installation</b></summary>

```bash
pip install 'railtracks[visual]'
```

</details>


<details open>
<summary><b>Set your API key</b></summary>

Railtracks loads a local `.env` file on import, save your provider keys there:

```bash
echo "OPENAI_API_KEY=sk-..." >> .env
```

</details>


<details open>
<summary><b>Your First Agent</b></summary>


```python
import railtracks as rt


# 1. Create tools (just functions with decorators!)
@rt.function_node
def count_characters(text: str, character: str) -> int:
    """Count occurrences of a character in text."""
    return text.count(character)


@rt.function_node
def word_count(text: str) -> int:
    """Count words in text."""
    return len(text.split())


# 2. Build an agent with tools
text_analyzer = rt.agent_node(
    "Text Analyzer",
    tool_nodes=[count_characters, word_count],
    llm=rt.llm.OpenAILLM("gpt-5.4-mini"),
    system_message="You analyze text using the available tools.",
)

# 3. Use it to solve the classic "How many r's in strawberry?" problem
text_flow = rt.Flow(name="Text Analysis Flow", entry_point=text_analyzer)

result = text_flow.invoke("How many 'r's are in 'strawberry'?")
print(result.text)
```

</details>


## LLM Support

Railtracks integrates with major model providers through a unified interface:

```python
# OpenAI
rt.llm.OpenAILLM("gpt-5.4-mini")

# Anthropic
rt.llm.AnthropicLLM("claude-sonnet-5")

# Local models
rt.llm.OllamaLLM("llama3")
```

Works with **OpenAI**, **Anthropic**, **Google**, **Azure**, and more. See the [full provider list](https://docs.railtracks.org/integrations/llms/providers/).

## Contributing

Railtracks is developed in the open. Contributions, bug reports, and feature requests are welcome via [GitHub Issues](https://github.com/RailtownAI/railtracks/issues).

<p align="center">
  <a href="https://docs.railtracks.org/documentation/getting_started/quickstart/">
    <img src="https://img.shields.io/badge/Quick_Start-4285F4?style=for-the-badge&logo=rocket&logoColor=white" alt="Quick Start" />
  </a>
  <a href="https://docs.railtracks.org/">
    <img src="https://img.shields.io/badge/Documentation-00D4AA?style=for-the-badge&logo=gitbook&logoColor=white" alt="Documentation" />
  </a>
  <a href="https://github.com/RailtownAI/railtracks/tree/main/examples">
    <img src="https://img.shields.io/badge/Examples-FF6B35?style=for-the-badge&logo=github&logoColor=white" alt="Examples" />
  </a>
  <a href="https://discord.gg/2JUb2TxjJv">
    <img src="https://img.shields.io/badge/Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Join Discord" />
  </a>
</p>

---

<sub>Licensed under MIT · Made by the Railtracks team</sub>
