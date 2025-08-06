<!--

                        INSTRUCTIONS FOR AUTHORS

=============================================================================
Remove these comment blocks when you no longer need the guidance.
-->

# Node Management

Provides the core abstractions and infrastructure for creating, executing, serialising and debugging Railtracks “nodes”—small, composable units of asynchronous work.

**Version:** 0.0.1 <!-- Bump on any externally-observable change. -->

## Table of Contents

- [1. Functional Overview](#1-functional-overview)
- [2. External Contracts](#2-external-contracts)
- [3. Design and Architecture](#3-design-and-architecture)
- [4. Related Files](#4-related-files)
- [CHANGELOG](#changelog)

---

## 1. Functional Overview

Railtracks workflows are expressed as graphs of *nodes*.  
The Node Management feature offers a complete, opinionated life-cycle for those nodes:

1. *Definition* – subclass `railtracks.nodes.Node` or use higher-level helpers (e.g. `NodeBuilder` or function-wrappers) to declare new node types.  
2. *Creation* – validate the new class with `node_creation.validation` and optionally register it with a registry.  
3. *Invocation* – execute a node asynchronously (`await node.tracked_invoke()`) while automatically capturing debug & latency data.  
4. *Introspection* – access `node.details` for rich runtime telemetry.  
5. *Serialisation* – convert a live node into a light-weight `NodeState` object that can cross process or network boundaries, then re-hydrate it with `.instantiate()`.  
6. *Tool exposure* – expose a node as an LLM-callable *tool* via the `ToolCallable` mix-in.

The following sections group the most common developer tasks.

### 1.1 Create a Simple Node

```python
from railtracks.nodes import Node

class Adder(Node[int]):
    @classmethod
    def name(cls) -> str:
        return "Adder"

    def __init__(self, a: int, b: int):
        super().__init__()
        self.a, self.b = a, b

    async def invoke(self) -> int:
        return self.a + self.b
```

### 1.2 Execute With Latency Tracking

```python
node = Adder(3, 4)
result = await node.tracked_invoke()
print(result)                             # 7
print(node.details["latency"].total_time) # seconds (float)
```

### 1.3 Pass Nodes Across Process Boundaries

```python
from railtracks.nodes import NodeState

state = NodeState(node)         # serialisable!
transport(state)                # send over IPC / network
new_node = state.instantiate()  # get a working copy
```

### 1.4 Build Variants Programmatically

```python
from railtracks.nodes import NodeBuilder

CustomAdder = (
    NodeBuilder(Adder, class_name="BigAdder")
    .override_attrs(name=lambda cls: "Big Adder")
    .build()
)
```

### 1.5 Expose as an LLM Tool

```python
class AdderTool(Adder):
    @classmethod
    def tool_info(cls):
        from railtracks.llm.tools import Tool, Parameter
        return Tool(
            name=cls.name(),
            description="Adds two integers",
            parameters=[
                Parameter(name="a", type="int", description="first operand"),
                Parameter(name="b", type="int", description="second operand"),
            ],
        )
```

## 2. External Contracts

Although node management is an internal runtime concern, other systems can interact with it via several stable surfaces.

### 2.1 CLI

| Command                                   | Description                              |
| ----------------------------------------- | ---------------------------------------- |
| `railtracks run <NodeClass> [args…]`      | Spawn a node in an isolated worker.      |
| `railtracks inspect <state.json>`         | Re-hydrate a `NodeState` file and print debug info. |

(See [`components/cli_entry_point.md`](../components/cli_entry_point.md) for the full specification.)

### 2.2 Environment Variables

| Name                         | Default | Purpose                                             |
| ---------------------------- | ------- | --------------------------------------------------- |
| `RT_NODE_DEBUG`              | `false` | When `true`, each node captures verbose debug data. |
| `RT_NODE_SERIALISATION_FMT`  | `json`  | Wire-format for `NodeState` objects.                |

### 2.3 Event Bus Messages

If [`features/task_execution.md`](../features/task_execution.md) is enabled, each `tracked_invoke` emits:

| Topic                | Payload                                     |
| -------------------- | ------------------------------------------- |
| `node.started`       | `{uuid, name, params}`                      |
| `node.finished`      | `{uuid, latency_ms, output_summary}`        |
| `node.failed`        | `{uuid, latency_ms, exception_type}`        |

## 3. Design and Architecture

### 3.1 Core Abstractions

| Class / Module                                                     | Responsibility                                                                     |
| ------------------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| `railtracks.nodes.Node`                                            | Abstract base; enforces async `invoke`, debug hooks, and tool-integration.         |
| `NodeState`                                                        | Portable, serialisable snapshot of a node.                                         |
| `DebugDetails`, `LatencyDetails`                                   | Typed containers recorded inside each node’s `details` dict.                       |
| `NodeBuilder` (`components/node_building.md`)                      | Meta-programming helper that fabricates new subclasses at runtime.                 |
| Validation modules (`node_creation.validation`, `node_invocation.validation`) | Static and runtime validation to keep nodes well-formed.                           |

#### Why Async Wrapping?

`Node.__init_subclass__` dynamically wraps the subclass’ `invoke` method:

```
if not asyncio.iscoroutinefunction(invoke):
    invoke = asyncio.to_thread(invoke)
```

This allows library authors to write sync code without sacrificing the async contract expected by the wider execution engine.

#### ToolCallable Mix-in

`Node` inherits from [`ToolCallable`](../components/tool_callable_node.md).  
This single-inheritance trick means *every* node can optionally advertise itself as an LLM “tool” by implementing `tool_info` and `prepare_tool`, without duplicating boiler-plate.

### 3.2 Data & Control Flow

```mermaid
flowchart TD
    subgraph Worker-Process
        A[Instantiate Node] -->|tracked_invoke| B[Record start time]
        B --> C[invoke()]
        C -->|await| D[return output]
        D --> E[Compute latency]
        E --> F[Populate DebugDetails]
        F --> G[Return output to caller]
    end
    G --> H[Coordinator / Caller]
```

### 3.3 Serialisation Strategy

1. `NodeState(node)` performs a **deepcopy** of the node (ensures pass-by-value).  
2. The instance is pickled / JSON-encoded (configurable).  
3. On the remote side `NodeState.instantiate()` returns a *shallow* reference copy—fast, avoids replaying constructor logic.

Trade-off: deep-copy serialises *all* attributes, so extremely large tensors or file handles should be stored in external object stores and fetched lazily.

### 3.4 Failure Semantics

• Any unhandled exception in `invoke` bubbles up unchanged; `tracked_invoke` still records latency and attaches the exception type to `details`.  
• Nodes guarantee *at-least-once* execution semantics; the surrounding task-execution feature is responsible for retries and idempotency.

### 3.5 Rejected Alternatives

| Alternative                                     | Reason Rejected                                                   |
| ------------------------------------------------| ----------------------------------------------------------------- |
| Enforcing `async def` at author-time            | Too intrusive for simple sync functions; runtime wrapping is safer. |
| ORMs / Dataclasses for serialisation            | Added heavy dependencies and poorer forward-compatibility.        |

## 4. Related Files

### 4.1 Related Component Files

- [`components/node_management.md`](../components/node_management.md): Detailed component-level API and examples of the `Node` base class.  
- [`components/node_building.md`](../components/node_building.md): Runtime subclass generation.  
- [`components/node_state_management.md`](../components/node_state_management.md): Low-level serialisation helpers.  
- [`components/node_creation_validation.md`](../components/node_creation_validation.md) & [`components/node_invocation_validation.md`](../components/node_invocation_validation.md): Static and runtime validators.  
- [`components/response_handling.md`](../components/response_handling.md): Response objects returned by many node subclasses.  
- [`components/tool_callable_node.md`](../components/tool_callable_node.md): Base class that integrates nodes with LLM tool-calling.

### 4.2 Related Feature Files

- [`features/node_interaction.md`](../features/node_interaction.md): Higher-level API for orchestrating multiple nodes.  
- [`features/task_execution.md`](../features/task_execution.md): Distributed executor which relies heavily on Node Management.  
- [`features/llm_integration.md`](../features/llm_integration.md): How the LLM subsystem makes use of nodes like `TerminalLLM`.  

### 4.3 External Dependencies

- [`typing-extensions`](https://pypi.org/project/typing-extensions/) – `Self`, `TypeVarTuple`, etc.  
- **Python ≥ 3.10** – structural pattern-matching used in validation modules.

---

## CHANGELOG

- **v0.0.1** (2024-04-30) [`<INITIAL_COMMIT>`]: Initial extraction from monolith into standalone feature document.