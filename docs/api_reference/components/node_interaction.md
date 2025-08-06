# Node Interaction

The Node Interaction component facilitates node execution and interaction within the Railtracks framework, supporting batch processing, synchronous and asynchronous calls, and streaming. It is designed to handle various execution patterns and ensure efficient communication between nodes.

**Version:** 0.0.1

**Component Contact:** @github_username

## Table of Contents

- [1. Purpose](#1-purpose)
- [2. Public API](#2-public-api)
- [3. Architectural Design](#3-architectural-design)
- [4. Important Considerations](#4-important-considerations)
- [5. Related Files](#5-related-files)
- [CHANGELOG](#changelog)

## 1. Purpose

The Node Interaction component is essential for executing nodes in different modes, such as batch processing, synchronous, and asynchronous calls. It also supports streaming, allowing for real-time data processing and communication between nodes.

### 1.1 Batch Processing

Batch processing allows for parallel execution of nodes over multiple iterables, improving efficiency and performance.

python
results = await call_batch(NodeA, ["hello world"] * 10)
for result in results:
    handle(result)


### 1.2 Synchronous and Asynchronous Calls

This component supports both synchronous and asynchronous node execution, providing flexibility in how nodes are called and managed.

python
# Asynchronous call
result = await call(NodeA, "hello world", 42)

# Synchronous call
result = call_sync(NodeA, "hello world", 42)


### 1.3 Streaming

Streaming enables real-time data processing by broadcasting messages to other nodes.

python
await broadcast("streaming data")


## 2. Public API



## 3. Architectural Design

The Node Interaction component is designed to handle various execution patterns and ensure efficient communication between nodes. It leverages asynchronous programming to manage node execution and streaming effectively.

### 3.1 Execution Patterns

- **Batch Processing:** Utilizes `asyncio.gather` to execute nodes in parallel, returning results in the order of the input iterables.
- **Synchronous and Asynchronous Calls:** Supports both modes of execution, with asynchronous calls using `asyncio` and synchronous calls managing event loops internally.
- **Streaming:** Uses a publisher-subscriber model to broadcast messages, ensuring real-time data processing.

## 4. Important Considerations

### 4.1 Dependencies & Setup

- Ensure that the `railtracks` package is properly installed and configured.
- The component relies on the `asyncio` library for managing asynchronous operations.

### 4.2 Performance & Limitations

- Batch processing is efficient for large datasets but may require careful management of resources to avoid bottlenecks.
- Synchronous calls should not be used within an already running event loop to prevent runtime errors.

### 4.3 State Management & Concurrency

- The component manages state using context objects, ensuring thread-safety and proper execution flow.

## 5. Related Files

### 5.1 Code Files

- [`batch.py`](../packages/railtracks/src/railtracks/interaction/batch.py): Handles batch processing of nodes.
- [`call.py`](../packages/railtracks/src/railtracks/interaction/call.py): Manages synchronous and asynchronous node calls.
- [`stream.py`](../packages/railtracks/src/railtracks/interaction/stream.py): Implements streaming functionality.

### 5.2 Related Component Files

- [`task_execution.md`](../components/task_execution.md): Details the task execution component, which interacts with node execution.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.

