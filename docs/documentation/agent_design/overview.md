## Introduction

Design and complexity of agent systems scales with the problem domain they are intended to solve. By definition, they can range from a single LLM answering questions all the way to a multi-agent architecture, with tools enabling interactions with databases and external services.

At its core, the design is two pronged:

1. Agent Level Design
2. Agent Interaction Design

## Core Concepts & Terminology

- **Node**: The fundamental execution block in Railtracks encapsulating logic (such as LLM prompts or Python functions).
- **Agent Node**: An LLM-powered node created via `rt.agent_node()` that manages prompt messages, model calls, and tools.
- **[Direct Invocation](../invocation/call.md)**: Executing a node directly using `await rt.call(node, ...)` without wrapped session management.
- **[Sequential Flow](../../tutorials/concepts/architectures/sequential.md)**: An architecture where tasks or nodes execute in sequence within a [`Flow`](../invocation/flows.md).

## Agent Level Design

This is where what we'd like to call "intra-agent" decisions come into play. Things such as choice of _LLM_, _System Message_, and _Tools_. Snippet below provides the most fundamental LLM-powered agent in Railtracks with no tool calling capabilities.

```python
--8<-- "docs/scripts/documentation/agent_design.py"
```
??? info "Parameters"
    - `name`: Optional name to give your agent. Will default to the node type if not provided

## Agent Interaction Design
This is where the connections between different agents and the rest of your code come into play. In Railtracks, for this connection we use the concept of [`Flows`](../invocation/flows.md) where you define these relationships. Read more at [Flow Invocation](../invocation/flows.md).
