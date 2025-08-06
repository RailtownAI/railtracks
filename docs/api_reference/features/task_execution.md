<!--
Feature Documentation – Task Execution

================================================================================
This document follows TEMPLATE_FEATURE.md and describes the “Task Execution” feature.
-->

# Task Execution

Enables reliable, observable, and pluggable execution of RailTracks **nodes** via
synchronous or asynchronous strategies, while surfacing lifecycle events through
the Pub/Sub system.

**Version:** 0.0.1 <!-- Bump on any externally-observable change. -->

## Table of Contents

- [1. Functional Overview](#1-functional-overview)
- [2. External Contracts](#2-external-contracts)
- [3. Design and Architecture](#3-design-and-architecture)
- [4. Related Files](#4-related-files)
- [CHANGELOG](#changelog)

---

## 1. Functional Overview

The Task Execution feature is responsible for turning a *logical* node
invocation (e.g. `rt.call_sync(MyNode, "hello")`) into concrete work that is
executed, monitored, and reported back to the caller.  It is intentionally
decoupled from the node graph and from I/O concerns so that new execution
strategies (threads, processes, remote workers, etc.) can be added without
changing user-facing code.

Key responsibilities:

1. Create an executable `Task` object that wraps a node invocation.
2. Select and apply an `ExecutionStrategy` (`asyncio`, `thread`, `process`, …).
3. Track job metadata (start/end times, status) through `CoordinatorState`.
4. Emit lifecycle messages (`RequestSuccess`, `RequestFailure`, …) on the
   Pub/Sub bus for observability and downstream consumers.
5. Offer a simple façade (`Session` helpers `call_sync`, `call_async`) for
   library users.

### 1.1 Executing a Node (synchronous helper)

```python
import railtracks as rt

# A session implicitly wires up a Coordinator and Publisher for us.
with rt.Session() as run:
    result = rt.call_sync(rt.nodes.MyNode, "Hello world!")
print(result)
```

Behind the scenes:

```
Session ──► Coordinator ──► AsyncioExecutionStrategy ──► Task.invoke()
         │               │                           │
         │               │◄──────── Pub/Sub messages ◄┘
         └── ExecutionInfo / RTState updated
```

### 1.2 Manual Coordination

Advanced users can bypass the high-level helpers to exert fine-grained control.

```python
from railtracks.execution.coordinator import Coordinator
from railtracks.execution.execution_strategy import AsyncioExecutionStrategy
from railtracks.execution.task import Task
from railtracks.pubsub.publisher import RTPublisher

publisher = RTPublisher()
coordinator = Coordinator(execution_modes={"async": AsyncioExecutionStrategy()})
coordinator.start(publisher)            # attach subscriber

task = Task(request_id="abc123", node=my_node)
response = await coordinator.submit(task, mode="async")  # returns RequestSuccess/Failure
```

### 1.3 Streaming & Observability

Attach a broadcast subscriber to stream real-time events:

```python
from railtracks.pubsub import stream_subscriber

def ui_handler(text: str):
    print(text)

with rt.Session(broadcast_callback=ui_handler) as run:
    rt.call_sync(rt.nodes.ChatNode, "Hi!")
```

The callback receives pretty-formatted log lines produced from
`RequestCompletionMessage.log_message()`.

---

## 2. External Contracts

The feature lives entirely inside the Python package; there are no public HTTP
endpoints.  The following contracts are relied upon by other features:

### 2.1 Pub/Sub Topics

| Message Class                               | Description                                  | Published By              |
| ------------------------------------------- | -------------------------------------------- | ------------------------- |
| `railtracks.pubsub.messages.RequestSuccess` | Node finished successfully.                  | `AsyncioExecutionStrategy`|
| `RequestFailure`                            | Node raised an exception.                    | `AsyncioExecutionStrategy`|
| `RequestCreation`                           | A new task was created (future extension).   | (planned)                 |
| `FatalFailure`                              | Irrecoverable coordinator failure.           | Coordinator               |

Consumers: Logging/Observability, UI streaming, **Session Management** (saves
state), and any user-supplied callback registered through `stream_subscriber()`.

### 2.2 Environment Variables & Flags

| Name                        | Default | Purpose                                                                     |
| --------------------------- | ------- | --------------------------------------------------------------------------- |
| `RAILTRACKS_EXECUTION_MODE` | `async` | Experimental override to force a global execution mode (not yet stable).    |

---

## 3. Design and Architecture

The Task Execution feature is a thin orchestration layer intentionally kept
separate from graph-building concerns so that execution tactics can evolve.

```mermaid
graph TD
  subgraph Feature Boundary
    Session -->|creates| Coordinator
    CoordinatorState -.-> Coordinator
    Coordinator -->|delegates| Strategy[ExecutionStrategy]
    Strategy --> Task
    Task --> NodeInvoke[Node.tracked_invoke()]
  end

  NodeInvoke -->|result| PubSubMessage[RequestSuccess / Failure]
  PubSubMessage -- broadcast --> RTPublisher
  RTPublisher -- subscriber --> Coordinator
  Coordinator -->|"end_job()"| CoordinatorState
```

### 3.1 Core Abstractions

• **Task** – Immutable wrapper pairing `request_id` with a `Node` instance.
  Provides `invoke()` that injects context (`update_parent_id`) then calls
  `Node.tracked_invoke()`, thereby ensuring audit logging is captured.

• **ExecutionStrategy (Strategy Pattern)** – Defines **how** a task runs.
  Current concrete class: `AsyncioExecutionStrategy`.  Future: `Threaded`,
  `Process`, distributed workers.

• **Coordinator (Command Invoker)** – Receives tasks, selects a strategy, tracks
  state, and listens to completion messages so that it can mark jobs *closed*.

• **CoordinatorState / Job** – In-memory, append-only record of job lifecycle
  used for diagnostics (`Session.info`) and persisted on run teardown.

### 3.2 Trade-offs & Rationale

| Decision                                   | Reasoning / Impact                                                              |
| ------------------------------------------ | --------------------------------------------------------------------------------|
| **Asyncio-first** execution                | Optimal for IO-bound LLM/API calls, simplest to implement; lacks GIL parallelism|
| Strategy Pattern instead of if/else flags  | Cleaner extension point; avoids Coordinator bloat                               |
| Pub/Sub for internal events                | Decouples execution from logging, UI, persistence; minimal runtime overhead     |
| No cross-thread execution yet              | Prevents tricky contextvars migration; revisit after stable single-event loop   |

### 3.3 Rejected Alternatives

* **Celery / external queue** – too heavy-weight for in-process graphs.
* **Direct Node invocation in Session** – would mix concerns and block future
  distributed execution.

---

## 4. Related Files

### 4.1 Related Component Files

- [`../components/task_execution.md`](../components/task_execution.md) – Low-level API reference for Coordinator, Task, and Execution Strategy.
- [`../components/pubsub_messaging.md`](../components/pubsub_messaging.md) – Defines message classes and publisher utilities used for lifecycle events.
- [`../components/session_management.md`](../components/session_management.md) – Describes how `Session` bootstraps a publisher and coordinator.

### 4.2 Related Feature Files

- [`../features/state_management.md`](../features/state_management.md) – Persists `CoordinatorState` and `ExecutionInfo` to disk.
- [`../features/logging_profiling.md`](../features/logging_profiling.md) – Subscribes to Pub/Sub messages for structured logs and performance metrics.

### 4.3 External Dependencies

- [`https://docs.python.org/3/library/asyncio.html`](https://docs.python.org/3/library/asyncio.html) – Standard library used by `AsyncioExecutionStrategy`.

---

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial extraction from monolithic
  documentation, added Architectural diagrams and External Contracts section.