## Introduction

Design and complexity of agent systems scales with the problem domain they are intended to solve. By definition, they can range from a single LLM answering questions all the way to a multi-agent architecture, with tools enabling interactions with databases and external services.

At its core, the design is two pronged:

1. Agent Level Design
2. Agent Interaction Design

## Building Blocks

Railtracks has a single execution primitive, the node, and two builders that produce one. These terms are used throughout the rest of the documentation, so they are worth reading once here.

### Node

A **node** is the unit Railtracks executes. It accepts inputs, runs, and returns an output, and Railtracks records every invocation of it in the [run](../invocation/flows.md#run) graph and exposes it to [middleware](middleware/overview.md). Agents, tools, and plain Python functions are all nodes, and that is what lets Railtracks treat them interchangeably: anything that is a node can be given to an agent as a tool, used as a [Flow](../invocation/flows.md) entry point, or called from inside another node with [`rt.call`](../invocation/call.md).

You do not subclass anything to make one. Two builders cover it: `rt.agent_node()` when the step needs a model to decide something, and `@rt.function_node` when the step is deterministic Python.

### Agent Node

An **agent node** is a node whose work is a call to an LLM. It is built with `rt.agent_node()` and holds the model, the system message, and the tools the model is allowed to call; at runtime it drives the tool-calling loop for you until the model produces a final answer.

Reach for an agent node when the step needs judgement, such as interpreting a vague request, choosing between tools, or writing prose. If the step has one correct implementation, like a calculation or an API call, write a [function node](tools/function_tools.md#what-a-function-node-is) instead and let an agent call it as a tool. Note that `rt.agent_node()` returns a class rather than an instance, which is why agents are named in PascalCase throughout these docs. [Agent Level Design](#agent-level-design) covers the choices you make when configuring one.

### Function Node

The other kind of node, built from one of your own Python functions, has a page of its own: [Function Tools](tools/function_tools.md#what-a-function-node-is).

## Agent Level Design

This is where what we'd like to "intra-agent" decisions come into play. Things such as choice of [_LLM_](../../integrations/llms/providers.md), _System Message_, [_Tools_](tools/function_tools.md), and [_Middleware_](middleware/overview.md). Snippet below provides the most fundamental LLM-powered agent in Railtracks with no tool calling capabilities.

```python
--8<-- "docs/scripts/documentation/agent_design.py"
```
??? info "Parameters"
    - `name`: Optional name to give your agent. Will default to the node type if not provided

## Agent Interaction Design
This is where the connections between different agents and the rest of your code come into play. In Railtracks, for this connection we use the concept of `Flows` where you define these relationships. Read more at [Flow Invocation](../invocation/flows.md).
