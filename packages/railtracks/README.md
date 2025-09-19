[![PyPI version](https://img.shields.io/pypi/v/railtracks)](https://github.com/RailtownAI/railtracks/releases)
[![Python Versions](https://img.shields.io/pypi/pyversions/railtracks?logo=python&)](https://pypi.org/project/railtracks/)
[![License](https://img.shields.io/pypi/l/railtracks)](https://opensource.org/licenses/MIT)
[![PyPI - Downloads](https://img.shields.io/pepy/dt/railtracks)](https://pypistats.org/packages/railtracks)
[![Docs](https://img.shields.io/badge/docs-latest-00BFFF.svg?logo=)](https://railtownai.github.io/railtracks/)
[![GitHub stars](https://img.shields.io/github/stars/RailtownAI/railtracks.svg?style=social&label=Star)](https://github.com/RailtownAI/railtracks)
[![Discord](https://img.shields.io/badge/Discord-Join-5865F2?logo=discord&logoColor=white)](https://discord.gg/h5ZcahDc)


## Helpful Links
<p align="center">
  <a href="https://railtownai.github.io/railtracks/" style="font-size: 30px; text-decoration: none;">📘 Documentation</a> <br>
  <a href="https://github.com/RailtownAI/railtracks/tree/main/examples/rt_basics" style="font-size: 30px; text-decoration: none;">🚀 Examples</a> <br>
  <a href="https://railtownai.github.io/railtracks/api_reference" style="font-size: 30px; text-decoration: none;">🛠 API Reference</a> <br>
  <a href="https://discord.gg/h5ZcahDc" style="font-size: 30px; text-decoration: none;">💬 Join Discord</a> <br>
</p>

## What is Railtracks?
**Railtracks** is a lightweight agentic LLM framework for building modular, multi-LLM workflows. Unlike other frameworks like **Langgraph** and **Google ADK**. Railtracks instead focuses on:

- Simple Python-first APIs -> no graphs, just regular Python code
- Built-in visualization and debugging tools -> understand and trace your agent flows visually
- Zero setup overhead -> run it like any other Python script without special directories or configs

| Feature                | Railtracks | LangGraph  | Google ADK |
| ---------------------- | ---------- | ---------- | ---------- |
| Python-first, no DSL   | ✅ Yes      | ❌ No       | ✅ Yes       |
| Built-in visualization | ✅ Yes      | ✅ Yes      | ⚠️ Limited|
| Simple Running         | ✅ Yes      | ✅ Yes     | ❌ No       |
| LLM-agnostic           | ✅ Yes      | ✅ Yes      | ✅ Yes      |
<!-- @import "[TOC]" {cmd="toc" depthFrom=1 depthTo=6 orderedList=false} -->

<!-- code_chunk_output -->

  - [Helpful Links](#helpful-links)
  - [What is Railtracks?](#what-is-railtracks)
  - [Quick Start](#quick-start)
    - [Step 1: Install the Library](#step-1-install-the-library)
    - [Step 2: Define a Tool](#step-2-define-a-tool)
- [Step 3. Create your agent (connecting your LLM)](#step-3-create-your-agent-connecting-your-llm)
    - [Step 4: Run Your Application](#step-4-run-your-application)
    - [Optional: Visualize the Run](#optional-visualize-the-run)

<!-- /code_chunk_output -->




Get started with either the quick start or via the [docs](https://railtownai.github.io/railtracks/)

## Quick Start

Build your first agentic system in just a few steps. Start by building an agent which solves the "how many `r`'s are in Strawberry?" problem. 

### Step 1: Install the Library

```bash
# Core library
pip install railtracks

# [Optional] CLI support for development and visualization
pip install railtracks-cli
```

### Step 2: Define a Tool

```python
import railtracks as rt

# Create your tool
@rt.function_node
def number_of_chars(text: str, character_of_interest: str) -> int:
    return text.count(character_of_interest)

@rt.function_node
def word_count(text: str) -> int:
    return len(text.split())
```

# Step 3. Create your agent (connecting your LLM)
```python
TextAnalyzer = rt.agent_node(
    tool_nodes={number_of_chars, word_count},
    llm=rt.llm.OpenAILLM("gpt-4o"), # use any model you want
    system_message=(
        "You are a text analyzer. You will be given a text and you should utilie the tools available to analyze it."
    ),
)
```

### Step 4: Run Your Application

```python
import asyncio

@rt.session
async def main():
    result = await rt.call(
        TextAnalyzer,
        rt.llm.MessageHistory([
            rt.llm.UserMessage("Hello world! This is a test of the Railtracks framework.")
        ])
    )
    print(result)

asyncio.run(main())
```

### Optional: Visualize the Run

```bash
railtracks init
railtracks viz
```

---

And just like that, you're up and running. The possibilities are endless.

---