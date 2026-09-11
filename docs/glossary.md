# Glossary

Railtracks uses a handful of ordinary words in a specific way. Each entry below says what a term means in one or two sentences, then links to the page that describes it in full.

!!! note "Contributing to this page"
    Entries here are pointers, not documentation: at most two sentences, always ending in a link, and no code or examples. If a term needs more than that to make sense, the linked section is too thin, so expand that section rather than this page.

## Building Blocks

### Agent

A system that pursues a goal on its own, deciding what to do next rather than following a fixed script. In Railtracks an agent is built as an [agent node](#agent-node). [What is an Agent?](tutorials/concepts/agents.md)

### Node

The unit Railtracks executes: it accepts inputs, runs, and returns an output. Agents, tools, and plain Python functions are all nodes, which is what lets Railtracks treat them interchangeably. [Building Blocks](documentation/agent_design/overview.md#node)

### Agent Node

A node whose work is a call to an LLM, built with `rt.agent_node()` and holding the model, system message and available tools. Reach for one when the step needs judgement rather than a fixed implementation. [Building Blocks](documentation/agent_design/overview.md#agent-node)

### Function Node

One of your own Python functions turned into a node by the `@rt.function_node` decorator. It is how deterministic work enters a graph, and how a function becomes a tool an agent can call. [Function Tools](documentation/agent_design/tools/function_tools.md#what-a-function-node-is)

### Tool

A capability an agent may choose to invoke, letting it act on the world instead of only producing text. In Railtracks a tool is any node passed to an agent as `tool_nodes=`. [What Is a Tool?](tutorials/concepts/tools.md#what-is-a-tool)

### Tool Manifest

The description an agent carries of how other agents may call it, given as `manifest=rt.ToolManifest(...)`. It is what lets an agent be used as a tool without a wrapper function. [Agents as Tools](documentation/agent_design/tools/agents_as_tools.md#2-tool-manifest)

### LLM

The language model an agent calls, configured through `rt.llm.*` and chosen per agent with `llm=`. See [LLMs as Agents](tutorials/concepts/agents.md#llms-as-agents) for the concept and [Providers](integrations/llms/providers.md) for the models Railtracks can reach.

### Structured Output

A response validated against a schema you supply as `output_schema=`, so an agent returns typed data rather than a string you have to parse. [Structured Output](documentation/agent_design/structured_extraction.md)

### Middleware

A layer that wraps a call to add behaviour around it, such as retries, logging or redaction, without changing the thing being called. Several can be attached to the same target, where they run as nested layers. [Middleware](documentation/agent_design/middleware/overview.md)

### Node Middleware

Middleware that wraps an entire node invocation, attached with `middleware=` on any node. [Node Middleware](documentation/agent_design/middleware/overview.md#node-middleware)

### Model Middleware

Middleware that wraps a single model call rather than the whole node, attached with `model_middleware=`. It applies only to agent nodes, since a function node never calls a model. [Model Middleware](documentation/agent_design/middleware/overview.md#model-middleware)

### Guardrail

Model middleware that inspects what goes into or comes out of a model call and decides whether to allow, change or reject it. Also referred to as a *guard* or a *rail*. [Guardrails](documentation/agent_design/middleware/guardrails/overview.md)

### Verifier

Node middleware that gates a call on a decision made outside the graph, which is how human-in-the-loop (**HIL**) review is built in Railtracks. [Verifiers](documentation/agent_design/middleware/verifiers/overview.md)

### Coupling

Attaching middleware to an existing node with `rt.couple()`, which returns a new node class rather than modifying the original. [Attaching Middleware](documentation/agent_design/middleware/overview.md#attaching-middleware)

### MCP

The Model Context Protocol, an open standard for exposing tools to models. Railtracks can both consume MCP tools and expose its own nodes as an MCP server. [Model Context Protocol](tutorials/concepts/mcp.md#what-is-model-context-protocol-mcp)

## Running Agents

### Flow

A named, reusable entry point for an agent graph, binding one entry point node to a fixed set of runtime options. It is the intended top level of a Railtracks program. [Flows](documentation/invocation/flows.md)

### Entry Point

The node a Flow starts from, given as `entry_point=`; every other node in the graph is reached from it. [Entry Point](documentation/invocation/flows.md#entry-point)

### Run

One execution of a Flow, started by `invoke` or `ainvoke`. It is the scope for context, timeouts and per-run budgets, and no two runs share state. [Run](documentation/invocation/flows.md#run)

### Direct Invocation

Calling a node yourself with `await rt.call(...)` instead of letting an agent decide to call it. It is how the steps inside a Flow are composed. [Direct Invocation](documentation/invocation/call.md)

### Context

Key-value state that any node in a run can read and write, used to pass data between agents without threading it through their messages. It lives only for the length of the run. [Global Context](documentation/advanced/context.md#what-is-global-context)

### Session

The record Railtracks writes for a run, stored under `.railtracks/data/sessions/` and read back by the visualizer and the evaluation tools. Prefer [run](#run) when referring to the execution itself. [Local Visualization](observability/agenthub/local_v2.md)

### Broadcasting

Sending live updates out of a running graph to a callback, so progress can be surfaced while the run is still going. [Broadcasting](observability/tracking/broadcasting.md)

### Streaming

Receiving a model's tokens as they are produced rather than waiting for the finished response, via `rt.astream`. [Streaming](integrations/llms/streaming.md#what-is-streaming)

## Architectures

### Sequential Flow

A Flow whose steps run in the order your Python code awaits them, rather than in an order a model chooses. [Sequential Flows](tutorials/concepts/architectures/sequential.md)

### Validation Loop

An architecture in which an agent evaluates its own output, applies the feedback and tries again until the result meets a bar. [Validation Loops](tutorials/concepts/architectures/validation_loop.md)

### Agent as Tool

Giving one agent another agent as a tool, so the caller delegates a sub-task instead of handling it itself. [Agents as Tools](documentation/agent_design/tools/agents_as_tools.md)

## Evaluation

### Evaluator

The component that runs an evaluation over a dataset and produces structured results. [Evaluators](evaluations/evaluators/evaluators.md)

### Metric

What an evaluation measures, either a category or a number, supplied to or fixed by an evaluator. [Metrics](evaluations/metrics/metrics.md)

## Retrieval

### Document

A loaded source file together with its metadata, before it has been split. [The Document object](retrieval/components/ingestion/base.md#the-document-object)

### Chunk

A slice of a Document sized for embedding and retrieval. [The Chunk object](retrieval/components/chunking/base.md#the-chunk-object)

### EmbeddedChunk

A Chunk together with the vector produced for it. [The EmbeddedChunk object](retrieval/components/embeddings/overview.md#the-embeddedchunk-object)

### Store

The backend that holds embedded chunks and answers similarity queries against them. [Data models](retrieval/components/stores/base.md#data-models)

### Retrieval Runtime

The object that ties loading, chunking, embedding and storage into one pipeline you can ingest into and query. [Retrieval Quickstart](retrieval/runtime/quickstart.md)
