<picture>
    <img alt="Railtracks Logo" src="docs/assets/logo.svg" width="80%">
</picture>

[![PyPI version](https://img.shields.io/pypi/v/railtracks.svg)](https://pypi.org/project/railtracks/)
[![Python Versions](https://img.shields.io/pypi/pyversions/railtracks.svg)](https://pypi.org/project/railtracks/)
[![License](https://img.shields.io/pypi/l/railtracks.svg)](https://github.com/RailtownAI/railtracks/blob/main/LICENSE)
[![Docs](https://img.shields.io/badge/docs-latest-blue.svg)](https://railtownai.github.io/railtracks/)
[![Release Notes](https://img.shields.io/github/release/RailtownAI/railtracks.svg)](https://github.com/RailtownAI/railtracks/releases)
[![GitHub stars](https://img.shields.io/github/stars/RailtownAI/railtracks.svg?style=social&label=Star)](https://github.com/RailtownAI/railtracks)




## Overview

**RailTracks** is a lightweight framework for building agentic systems; modular, intelligent agents that can be composed to solve complex tasks more effectively than any single module could.

The framework supports the entire lifecycle of agentic development: building, testing, debugging, and deploying. Its core principle is modularity, your systems are constructed from reusable, modular components.

---

### Step 1: Installation

```bash
# Core library
pip install railtracks

# [Optional] CLI support for development and visualization
pip install railtracks-cli
```

## Contributing

We welcome contributions of all kinds! Check out our [contributing guide](./CONTRIBUTING.md) to get started.


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
