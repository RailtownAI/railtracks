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

<div align="center">

</div>

## What is Railtracks?

Railtracks is a Python framework for building agentic systems. Agent behavior, tools, and multi-step flows are defined entirely in standard Python — using the control flow and abstractions you already know.


```python
import railtracks as rt

# Define a tool (just a function!)
def get_weather(location: str) -> str:
    return f"It's sunny in {location}!"

# Create an agent with tools
agent = rt.agent_node(
    "Weather Assistant",
    tool_nodes=(rt.function_node(get_weather)),
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You help users with weather information."
)

# Run it
flow = rt.Flow(name="Weather Flow", entry_point=agent)
result = await flow.invoke("What's the weather in Paris?")
print(result.text)  # "Based on the current data, it's sunny in Paris!"
```

Execution order, branching, and looping are expressed using standard Python control flow.

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
agent = rt.agent_node(
    "Assistant",
    tool_nodes=[my_tool, api_call]
)
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

See the [Observability documentation](https://railtownai.github.io/railtracks/observability/visualization/) for setup and usage.

</td>
</tr>
</table>

</div>

## Quick Start

<details open>
<summary><b>Installation</b></summary>

```bash
pip install railtracks railtracks[cli]
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
    tool_nodes=(count_characters, word_count),
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You analyze text using the available tools."
)

# 3. Use it to solve the classic "How many r's in strawberry?" problem
text_flow = rt.Flow(
  name="Text Analysis Flow"
  entry_point=text_analyzer
)

text_flow.invoke("How many 'r's are in 'strawberry'?")
```

</details>


## LLM Support

Railtracks integrates with major model providers through a unified interface:

```python
# OpenAI
rt.llm.OpenAILLM("gpt-5")

# Anthropic
rt.llm.AnthropicLLM("claude-4-6-sonnet")

# Local models
rt.llm.OllamaLLM("llama3")
```

Works with **OpenAI**, **Anthropic**, **Google**, **Azure**, and more. See the [full provider list](https://railtownai.github.io/railtracks/llm_support/providers/).

## Contributing

Railtracks is developed in the open. Contributions, bug reports, and feature requests are welcome via [GitHub Issues](https://github.com/RailtownAI/railtracks/issues).

<p align="center">
  <a href="https://railtownai.github.io/railtracks/quickstart/quickstart/">
    <img src="https://img.shields.io/badge/Quick_Start-4285F4?style=for-the-badge&logo=rocket&logoColor=white" alt="Quick Start" />
  </a>
  <a href="https://railtownai.github.io/railtracks/">
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