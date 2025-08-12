# RailTracks

## Overview

**RailTracks** is a lightweight framework for building agentic systems; modular, intelligent agents that can be composed to solve complex tasks more effectively than any single module could.

The framework supports the entire lifecycle of agentic development: building, testing, debugging, and deploying. Its core principle is modularity, your systems are constructed from reusable, modular components.

---

## Why RailTracks?

Many frameworks for building LLM-powered applications focus on pipelines, chains, or prompt orchestration. While effective for simple use cases, they quickly become brittle or overly complex when handling asynchronous tasks, multi-step reasoning, and heterogeneous agents.

**RailTracks was designed from the ground up with the developer in mind to support real-world agentic systems**, with an emphasis on:

* **Programmatic structure without rigidity** – Unlike declarative workflows (e.g., LangChain), RailTracks encourages clean Pythonic control flow.
* **Agent-first abstraction** – Inspired by real-world coordination, RailTracks focuses on defining smart agents that collaborate via tools—not just chaining LLM calls.
* **Automatic Parallelism** – All executions are automatically parallelized where possible, freeing you from managing threading or async manually.
* **Transparent Execution** – Includes integrated logging, history tracing, and built-in visualizations to show exactly how your system behaves.
* **Minimal API** – The small configurable API makes life a breeze compared to other tools. No magic.
* **Visual Insights** – Graph-based visualizations help you understand data flow and agent interactions at a glance.
* **Pluggable Models** – Use any LLM provider: OpenAI, open-weight models, or your own local inference engine.

Where frameworks like LangGraph emphasize pipelines, RailTracks aims to be the developer-friendly sweet spot: powerful enough for complex systems, but simple enough to understand, extend, and debug.

---

## Quick Start

Build your first agentic system in just a few steps.

### Step 1: Install the Library

```bash
# Core library
pip install railtracks

# [Optional] CLI support for development and visualization
pip install railtracks-cli
```

### Step 2: Define Your Modular Components

```python
import railtracks as rt

def number_of_chars(text: str) -> int:
    return len(text)

def number_of_words(text: str) -> int:
    return len(text.split())

def number_of_characters(text: str, character_of_interest: str) -> int:
    return text.count(character_of_interest)

TotalNumberChars = rt.function_node(number_of_chars)
TotalNumberWords = rt.function_node(number_of_words)
CharacterCount = rt.function_node(number_of_characters)

TextAnalyzer = rt.agent_node(
    tool_nodes={TotalNumberChars, TotalNumberWords, CharacterCount},
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
    system_message=(
        "You are a text analyzer. You will be given a text and return the number of characters, "
        "the number of words, and the number of occurrences of a specific character."
    ),
)
```

### Step 3: Run Your Application

```python
import railtracks as rt

result = rt.call_sync(
    TextAnalyzer,
    rt.llm.MessageHistory([
        rt.llm.UserMessage("Hello world! This is a test of the RailTracks framework.")
    ])
)
print(result)
```

### Step 4: \[Optional] Visualize the Run

```bash
railtracks init
railtracks viz
```

> *(Insert example visualization image here)*

And just like that, you're up and running. The possibilities are endless.

---

## Contributing

We welcome contributions of all kinds! Check out our [contributing guide](./CONTRIBUTING.md) to get started.
