## Introduction

Design and complexity of agent systems scales with the problem domain they are intended to solve. By definition, they can range from a single LLM answering questions all the way to a multi-agent architecture, with tools enabling interactions with databases and external services.

At its core, the design is two pronged:

1. Agent Level Design
2. Agent Interaction Design

## Agent Level Design

Agent-level design covers the behavior of one executable unit, including its model, system message, tools, and middleware.

### Node

A **Node** is Railtracks' executable building block. It defines an invocation contract: it accepts inputs, runs its `invoke` method through Railtracks' execution and middleware machinery, and produces an output. Agent logic and ordinary Python functions can both be represented as nodes, which lets Railtracks compose and track them in the same way.

You will usually create a Node with a builder such as `rt.agent_node()` or `@rt.function_node` instead of subclassing `Node` directly. Use a function node for deterministic Python work and an Agent Node when the work requires an LLM.

### Agent Node

An **Agent Node** is a Node class created by `rt.agent_node()`. It sends messages to a configured LLM and can include a system message, tools, structured output, and middleware. The example below creates a minimal Agent Node with no tools:

```python
--8<-- "docs/scripts/documentation/agent_design.py"
```
??? info "Parameters"
    - `name`: Optional name to give your agent. Will default to the node type if not provided

## Agent Interaction Design
Agent-interaction design covers how nodes call one another and how your application starts the resulting graph. Use [Direct Invocation](../invocation/call.md) for a single call or for explicit async composition. Use a [Flow](../invocation/flows.md) when you want a reusable, configured entry point. A [Sequential Flow](../../tutorials/concepts/architectures/sequential.md) is one Flow architecture that invokes nodes in a fixed order.
