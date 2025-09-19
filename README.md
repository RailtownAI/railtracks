# Railtracks

<p align="center">
    <img alt="Railtracks Logo" src="docs/assets/logo.svg" width="50%">
</p>

[![PyPI version](https://img.shields.io/pypi/v/railtracks?label=release)](https://github.com/RailtownAI/railtracks/releases)
[![License](https://img.shields.io/pypi/l/railtracks)](https://opensource.org/licenses/MIT)
[![PyPI - Downloads](https://img.shields.io/pepy/dt/railtracks)](https://pypistats.org/packages/railtracks)
[![Docs](https://img.shields.io/badge/docs-latest-00BFFF.svg?logo=openbook)](https://railtownai.github.io/railtracks/)
[![GitHub stars](https://img.shields.io/github/stars/RailtownAI/railtracks.svg?style=social&label=Star)](https://github.com/RailtownAI/railtracks)
[![Discord](https://img.shields.io/badge/Discord-Join-5865F2?logo=discord&logoColor=white)](https://discord.gg/h5ZcahDc)

## Helpful Links
<p align="center">
  <a href="https://railtownai.github.io/railtracks/" style="font-size: 30px; text-decoration: none;">📘 Documentation</a>
  <a href="https://github.com/RailtownAI/railtracks/tree/main/examples/rt_basics" style="font-size: 30px; text-decoration: none;">🚀 Examples</a>
</p>

## Overview

**Railtracks** is a lightweight framework for building agentic systems - modular, intelligent agents that can work together to solve complex tasks more effectively than any single module could.

**Railtracks-CLI** is a command-line tool designed to visualize your Railtracks runs. It's lightweight and can be run locally with **no sign-up required**.

---

## Installation

```bash
# Core library
pip install railtracks

# [Optional] CLI support for development and visualization
pip install railtracks-cli
```

## Contributing

We welcome contributions of all kinds! Get started by checking out our [contributing guide](./CONTRIBUTING.md).

---

## Why Railtracks?

Many frameworks for building LLM-powered applications focus on pipelines, chains, or prompt orchestration. While effective for simple use cases, they can become brittle or overly complex when handling asynchronous tasks, multi-step reasoning, and heterogeneous agents.

**Railtracks is designed with developers in mind to support real-world agentic systems** with an emphasis on:

* **Programmatic structure without rigidity** – Unlike declarative workflows (e.g., LangChain), Railtracks encourages clean, Pythonic control flow.
* **Agent-first abstraction** – Inspired by real-world coordination, Railtracks focuses on defining smart agents that collaborate via tools, not just chaining LLM calls.
* **Automatic Parallelism** – Executions are automatically parallelized when possible, freeing you from managing threading or async manually.
* **Transparent Execution** – Integrated logging, history tracing, and built-in visualizations show exactly how your system behaves.
* **Minimal API** – The small, configurable API simplifies your workflow compared to other tools. No magic.
* **Visual Insights** – Graph-based visualizations help you understand data flow and agent interactions at a glance.
* **Pluggable Models** – Use any LLM provider: OpenAI, open-weight models, or your own local inference engine.

While frameworks like LangGraph emphasize pipelines, Railtracks aims to strike the perfect balance: powerful enough for complex systems, yet simple enough to understand, extend, and debug.