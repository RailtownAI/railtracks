# Railtracks

<!--Happy Coding ◊ -->

<p align="center">
  <img alt="Railtracks Space Banner" src="https://raw.githubusercontent.com/RailtownAI/railtracks/main/docs/assets/hero-banner.svg" width="100%">
</p>

<h3 align="center">
  Agents in minutes • Zero config • Local visualization • Pure Python
</h3>

<br>

<p align="center">
  <a href="#-quick-start">
    <img src="https://img.shields.io/badge/Quick_Start-4285F4?style=for-the-badge&logo=rocket&logoColor=white" alt="Quick Start" />
  </a>
  <a href="https://railtownai.github.io/railtracks/">
    <img src="https://img.shields.io/badge/Documentation-00D4AA?style=for-the-badge&logo=gitbook&logoColor=white" alt="Documentation" />
  </a>
  <a href="https://github.com/RailtownAI/railtracks/tree/main/examples">
    <img src="https://img.shields.io/badge/Examples-FF6B35?style=for-the-badge&logo=github&logoColor=white" alt="Examples" />
  </a>
  <a href="https://discord.gg/h5ZcahDc">
    <img src="https://img.shields.io/badge/Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Join Discord" />
  </a>
</p>

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

---

## ✨ What is **Railtracks**?

Easy agent building, for no one but **YOU**: Create deployable complex agents using simple, Pythonic style interface with natural control flow.

<!-- Add an empty line or a horizontal rule to ensure separation -->
<br>


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

**That's it.** No complex configurations, no learning proprietary syntax. Just Python.

---

## 🎯 Why Railtracks?

<div align="center">

<table>
<tr>
<td width="50%" valign="top">

#### 🐍 **Pure Python Experience**
```python
# Write agents like regular functions
@rt.function_node
def my_tool(text: str) -> str:
    return process(text)
```
- ✅ No YAML, no DSLs, no magic strings
- ✅ Use your existing debugging tools
- ✅ IDE autocomplete & type checking

</td>
<td width="50%" valign="top">

#### 🔧 **Tool-First Architecture**
```python
# Any function becomes a tool
agent = rt.agent_node(
    "Assistant",
    tool_nodes=(my_tool, api_call)
)
```
- ✅ Instant function-to-tool conversion
- ✅ Seamless API/database integration
- ✅ MCP protocol support

</td>
</tr>
<tr>
<td width="50%" valign="top">

#### ⚡ **Look Familiar?**
```python
# Smart parallelization built-in 
# with interface similar to asyncio
result = await rt.call(agent, query)
```
- ✅ Easy to learn standardized interface
- ✅ Built-in validation, error handling & retries
- ✅ Auto-parallelization management

</td>
<td width="50%" valign="top">

#### 👁️ **Transparent by Design**
```bash
railtracks viz  # See everything
```
- ✅ Real-time execution visualization
- ✅ Complete execution history
- ✅ Debug like regular Python code

</td>
</tr>
</table>

</div>

---

## 🚀 Quick Start

<details open>
<summary><b>📦 Installation</b></summary>

```bash
pip install railtracks railtracks[cli]
```
</details>


<details open>
<summary><b>⚡ Your First Agent in 5 Min</b></summary>


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

<details open>
<summary><b>📊 Visualize Agent locally with a simple command</b></summary>


```bash
railtracks init  # Setup visualization (one-time)
railtracks viz   # See your agent in action
```

<p align="center">
  <video src="https://railtracksstorage.blob.core.windows.net/railtrackswebsite/Visualizer.mp4" controls width="90%"></video>
  <br>
  <em>🔍 See every step of your agent's execution in real-time</em>
</p>

</details>

---

## 🌟 What Makes Railtracks Special?

A lightweight agentic LLM framework for building modular, multi-LLM workflows with a focus on simplicity and developer experience.

<div align="center">

| Feature | Railtracks
|:--------|:----------:|
| **🐍 Python-first, no DSL** | ✅ |
| **📊 Built-in visualization** | ✅ |
| **⚡ Zero setup overhead** | ✅ |
| **🔄 LLM-agnostic** | ✅ |

</div>

---

## 🔗 Universal LLM Support

Switch between providers effortlessly:

```python
# OpenAI
rt.llm.OpenAILLM("gpt-4o")

# Anthropic
rt.llm.AnthropicLLM("claude-3-5-sonnet")

# Local models
rt.llm.OllamaLLM("llama3")
```

Works with **OpenAI**, **Anthropic**, **Google**, **Azure**, and more! Check out our neatly crafted [docs](https://railtownai.github.io/railtracks/llm/).

## 🛠️ Powerful Features

<div align="center">

<table>
<tr>
<td width="50%" valign="top">

### 📦 Rich Tool Ecosystem

Use existing tools or create your own:

- ✅ **Built in Tools** RAG, CoT, etc.
- ✅ **Functions** → Tools automatically
- ✅ **MCP Integration** as client or as server
- ✅ **Agents as Tools** → agent cluster

</td>
<td width="50%" valign="top">

### 🔍 Built-in Observability

Debug and monitor with ease:

- ✅ Real-time execution graphs
- ✅ Performance metrics
- ✅ Error tracking & debugging
- ✅ Local visualization
- ✅ Session management
- ✅ **No signup required!**

</td>
</tr>
</table>

</div>

---

## 📚 Learn More

<div align="center">

<table>
<tr>
<td align="center" width="20%">
<a href="https://railtownai.github.io/railtracks/">
<img src="https://img.icons8.com/fluency/96/000000/book.png" width="64" height="64" alt="Documentation"/>
<br><b>Documentation</b>
</a>
<br>
<sub>Complete guides & API reference</sub>
</td>
<td align="center" width="20%">
<a href="https://railtownai.github.io/railtracks/quickstart/quickstart/">
<img src="https://img.icons8.com/fluency/96/000000/rocket.png" width="64" height="64" alt="Quickstart"/>
<br><b>Quickstart</b>
</a>
<br>
<sub>Up and running in 5 minutes</sub>
</td>
<td align="center" width="20%">
<a href="https://github.com/RailtownAI/railtracks/tree/main/examples">
<img src="https://img.icons8.com/fluency/96/000000/code.png" width="64" height="64" alt="Examples"/>
<br><b>Examples</b>
</a>
<br>
<sub>Real-world implementations</sub>
</td>
<td align="center" width="20%">
<a href="https://discord.gg/h5ZcahDc">
<img src="https://img.icons8.com/fluency/96/000000/discord-logo.png" width="64" height="64" alt="Discord"/>
<br><b>Discord</b>
</a>
<br>
<sub>Get help & share creations</sub>
</td>
<td align="center" width="20%">
<a href="./CONTRIBUTING.md">
<img src="https://img.icons8.com/fluency/96/000000/handshake.png" width="64" height="64" alt="Contributing"/>
<br><b>Contributing</b>
</a>
<br>
<sub>Help make us better</sub>
</td>
</tr>
</table>

</div>

---



## 🚀 Ready to Build?

```bash
pip install railtracks[cli]
```
<div align="center">

<br>

## ✨ Join developers across the world building the future with AI agents

<br>

<a href="https://github.com/RailtownAI/railtracks/stargazers">
  <img src="https://img.shields.io/badge/⭐_STAR_THIS_REPO-FFD700?style=for-the-badge&logo=github&logoColor=000" alt="Star this repo" />
</a>

<br><br>

**You grow, we grow - Railtracks will expand with your ambitions.**

<br>

---

<sub>Made with lots of ❤️ and ☕ by the ◊Railtracks◊ team • Licensed under MIT • [Report Bug](https://github.com/RailtownAI/railtracks/issues) • [Request Feature](https://github.com/RailtownAI/railtracks/issues)</sub>

</div>
