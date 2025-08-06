<!--
                         FEATURE DOCUMENTATION
=============================================================================

Authoring notes:
• Follow TEMPLATE_FEATURE.md guidance.
• Keep explanations high-level here; component-level details live in their own
  docs and are linked where needed.
• Update CHANGELOG on any externally observable change.
-->

# Node Interaction

Uniform, high-level APIs for invoking Railtracks nodes—individually or in batches—both synchronously and asynchronously, with first-class support for streaming intermediate outputs.

**Version:** 0.0.1 <!-- bump on any externally-observable change -->

---

## Table of Contents

- [1. Functional Overview](#1-functional-overview)
- [2. External Contracts](#2-external-contracts)
- [3. Design and Architecture](#3-design-and-architecture)
- [4. Related Files](#4-related-files)
- [CHANGELOG](#changelog)

---

## 1. Functional Overview

`railtracks.interaction` exposes four helper functions that cover the entire node-execution life-cycle:

| Helper                         | Purpose                                                     |
| ------------------------------ | ----------------------------------------------------------- |
| `await call()`                 | Asynchronous single-node invocation (preferred).           |
| `call_sync()`                  | Blocking wrapper around `call()` for non-async code paths. |
| `await call_batch()`           | Parallel fan-out over multiple iterables.                  |
| `await broadcast()`            | Stream a chunk to the current node’s subscribers.          |

These helpers work **inside or outside** an active `rt.Session()`—they handle context boot-strapping transparently.

### 1.1 Single Node Invocation

Run a node once, await its result.

```python
import railtracks as rt
from my_nodes import GreeterNode

async def main():
    greeting = await rt.call(GreeterNode, "Alice")
    print(greeting)               # → "Hello Alice!"
```

`call()` returns a coroutine; schedule several of them to run concurrently:

```python
tasks = [rt.call(GreeterNode, name) for name in ["Ada", "Grace", "Linus"]]
results = await asyncio.gather(*tasks)
```

#### Synchronous Wrapper

For legacy / synchronous scripts:

```python
result = rt.call_sync(GreeterNode, "Bob")
```

Attempting to invoke `call_sync()` **inside** an already running `asyncio` loop raises an explanatory `RuntimeError`.

### 1.2 Batch Invocation

Map a node over *N* sets of arguments in parallel and preserve input order.

```python
names = ["Anna", "Ben", "Cara"]
results = await rt.call_batch(GreeterNode, names)
```

Internally this is a thin wrapper around `asyncio.gather()` with `return_exceptions=True` by default, so exceptions are gathered rather than raised prematurely.

### 1.3 Streaming

Push partial results downstream—ideal for token-by-token LLM streaming or status updates.

```python
await rt.broadcast("chunk-1")
await rt.broadcast("chunk-2")
```

Consumers attach any callable (sync **or** async) via `ExecutorConfig.subscriber`; see [`components/pubsub_messaging.md`](../components/pubsub_messaging.md#31-core-components) for subscription utilities.

### 1.4 Session-less Usage

All helpers auto-create a throw-away runtime when invoked outside a `rt.Session()`:

```python
# ✅ valid – automatic Session()
result = rt.call_sync(GreeterNode, "Eve")
```

### 1.5 Timeout & Cancellation

`rt.set_config(timeout=...)` sets a *global* per-request timeout; hitting it raises `GlobalTimeOutError`.  
Inside a node you may still raise `asyncio.TimeoutError` for fine-grained control—`call()` distinguishes the two cases.

---

## 2. External Contracts

Node Interaction itself does **not** expose HTTP endpoints or CLI commands; instead it relies on the Pub/Sub infrastructure it shares with the rest of Railtracks.

### 2.1 Pub/Sub Messages

| Message Type                               | Produced When                                        | Docs |
| ------------------------------------------ | ---------------------------------------------------- | ---- |
| `RequestCreation`                          | A new node is about to start.                       | [`pubsub_messaging`](../components/pubsub_messaging.md) |
| `RequestSuccess`, `RequestFailure`         | Node finished (successfully / with error).          | ″ |
| `Streaming`                                | `broadcast()` is called.                            | ″ |
| `FatalFailure`                             | Unrecoverable framework error detected.             | ″ |

Subscribers typically register through `RTPublisher.listener()`.

### 2.2 Configuration Flags

| Name                        | Type    | Default | Effect                                   |
| --------------------------- | ------- | ------- | ---------------------------------------- |
| `ExecutorConfig.timeout`    | float   | `30.0`  | Hard deadline enforced by `call()` top-level wrapper. |
| `ExecutorConfig.subscriber` | callable| —       | Callback receiving `Streaming` messages. |

Configure via `rt.set_config(...)` **before** spawning nodes.

---

## 3. Design and Architecture

Node Interaction is purposely small but sits at the nexus of multiple slow-changing contracts (context, pub/sub, executor config). The following diagram highlights the control flow when a **top-level** `call()` is issued.

```mermaid
sequenceDiagram
    participant User
    participant call() as call()/call_batch()
    participant Context as Context<br/>(central.py)
    participant Pub as RTPublisher
    participant Coord as Task Coordinator
    participant Node as Target Node

    User->>call(): invoke
    call()->>Context: ensure Session & Publisher
    activate Pub
    call()->>Pub: publish RequestCreation
    Pub->>Coord: (subscription) new task
    par Node execution
        Coord->>Node: invoke
        Node-->>Pub: Streaming (optional)
    end
    Node-->>Coord: result / exception
    Coord-->>Pub: RequestSuccess / RequestFailure
    Pub-->>call(): message filtered via request_id
    deactivate Pub
    call()-->>User: final result or raised error
```

### 3.1 Key Design Decisions & Trade-offs

1. **Single Entry Surface**  
   Four public helpers cover 99 % of invocation patterns; remaining power-user needs (e.g., custom execution strategies) live in [`features/task_execution.md`](../features/task_execution.md).

2. **Context-Aware Behaviour**  
   - No context → spin up temporary runner so library remains usable in REPL scripts.  
   - Active *but inactive* context (i.e., top-level node) → `_start()` performs publisher life-cycle & timeout enforcement.  
   - Active *and* running context (nested node) → `_run()` skips extra book-keeping for efficiency.

3. **Message Filtering**  
   To avoid cross-talk with concurrent requests, `call()` installs a per-request `listener()` whose predicate matches the generated `request_id`.

4. **Timeout Handling**  
   Differentiates *framework* timeout (`GlobalTimeOutError`) from user-land `asyncio.TimeoutError`, preserving semantics.

5. **Sync Wrapper Safety**  
   `call_sync()` detects an already running loop and fails fast, preventing dead-locks that plague naïve `asyncio.run()` wrappers.

6. **Batch Determinism**  
   Results keep **input ordering** even though workers run concurrently; callers thus avoid cumbersome index mapping.

7. **Streaming Simplicity**  
   `broadcast()` is a deliberate one-liner that just publishes `Streaming`—no extra abstractions until proven necessary.

### 3.2 Rejected Alternatives

| Alternative                               | Reason for Rejection |
| ----------------------------------------- | -------------------- |
| Exposing raw `RTPublisher` APIs to users  | Too low-level; duplicates logic for request tracking. |
| Auto-retrying failed nodes in `call_batch`| Responsibility better handled by orchestration layer; keeps this component stateless. |
| Allowing `call_sync()` inside event loop  | Leads to blocking calls that stall the loop; explicit error is safer. |

---

## 4. Related Files

### 4.1 Related Component Files

- [`components/node_interaction.md`](../components/node_interaction.md) – API reference & low-level implementation.
- [`components/pubsub_messaging.md`](../components/pubsub_messaging.md) – message types and publisher utilities used under the hood.
- [`components/context_management.md`](../components/context_management.md) – context & executor configuration accessed by helpers.
- [`components/task_execution.md`](../components/task_execution.md) – coordinator and execution strategies that run the actual work.

### 4.2 Related Feature Files

- [`features/task_execution.md`](../features/task_execution.md) – drives job scheduling and integrates with Node Interaction.
- [`features/state_management.md`](../features/state_management.md) – persists node results and context if `ExecutorConfig.save_state=True`.

### 4.3 External Dependencies

None beyond Python ≥3.9 standard library; all intra-framework communication leverages Railtracks’ own Pub/Sub implementation.

---

## CHANGELOG

- **v0.0.1** (2024-06-05) [`<INITIAL>`]: Initial public documentation.