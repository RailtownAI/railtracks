## Introduction

Design and complexity of agent systems scales with the problem domain they are intended to solve. By definition, they can range from a single LLM answering questions all the way to a multi-agent architecture, with tools enabling interactions with databases and external services.

At its core, the design is two pronged:

1. Agent Level Design
1. Agent Interaction Design

## Agent Level Design

This is where what we'd like to "intra-agent" decisions come into play. Things such as choice of *LLM*, *System Message*, and *Tools*. Snippet below provides the most fundamental LLM-powered agent in Railtracks with no tool calling capabilities.

```python
import railtracks as rt

SimpleChatAgent = rt.agent_node(
    name="SimpleChatAgent",
    system_message="You are Clippy, a helpful assistant that provides answers to user questions.",
    llm=rt.llm.GeminiLLM("gemini-3.8-flash")
)
```

Parameters

- `name`: Optional name to give your agent. Will default to the node type if not provided

## Agent Interaction Design

This is where the connections between different agents and the rest of your code come into play. In Railtracks, for this connection we use the concept of `Flows` where you define these relationships. Read more at [Flow Invocation](https://docs.railtracks.org/documentation/invocation/flows/index.md).
