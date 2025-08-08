# Task Execution

The Task Execution component is responsible for managing task execution strategies and job coordination, supporting different execution models like asyncio and threads.

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

The Task Execution component is designed to handle the execution of tasks using various strategies, such as asyncio and threading. It coordinates the execution of tasks, manages their lifecycle, and ensures that tasks are executed according to the specified strategy.

### 1.1 Task Submission and Execution

This use case involves submitting a task to the coordinator for execution using a specified execution strategy.

python
from railtracks.execution.coordinator import Coordinator
from railtracks.execution.execution_strategy import AsyncioExecutionStrategy
from railtracks.execution.task import Task
from railtracks.pubsub.messages import ExecutionConfigurations

# Initialize the execution strategy
execution_modes = {
    ExecutionConfigurations.ASYNCIO: AsyncioExecutionStrategy(),
}

# Create a coordinator
coordinator = Coordinator(execution_modes=execution_modes)

# Define a task
task = Task(request_id="123", node=my_node)

# Submit the task for execution
await coordinator.submit(task, ExecutionConfigurations.ASYNCIO)


### 1.2 Job Management

This use case demonstrates how to manage jobs within the coordinator, including adding and ending jobs.

python
from railtracks.execution.coordinator import CoordinatorState, Job
from railtracks.execution.task import Task

# Create a coordinator state
state = CoordinatorState.empty()

# Define a task
task = Task(request_id="123", node=my_node)

# Add a job
state.add_job(task)

# End a job
state.end_job(request_id="123", result="success")


## 2. Public API

### `class CoordinatorState`
A simple object that stores the state of the coordinator in terms of the jobs it has and is currently processing.

The API supports simple operations that will allow you to interact with the jobs.

#### `.__init__(self, job_list)`
Class constructor.

#### `.empty(cls)`
Creates an empty CoordinatorState instance.

One which no jobs have been completed

#### `.add_job(self, task)`
Adds a job to the coordinator state.

Args:
    task (Task): The task to create a job from.

#### `.end_job(self, request_id, result)`
End a job with the given request_id and result.


---
### `class Coordinator`
The coordinator object is the concrete invoker of tasks that are passed into any of the configured execution strategies.

#### `.__init__(self, execution_modes)`
Class constructor.

#### `.start(self, publisher)`
Starts the coordinator by attaching any relevant subscribers to the provided publisher.

#### `.handle_item(self, item)`
The basic handler to attach to the RequestCompletionPublisher.

#### `.submit(self, task, mode)`
Submits a task to the coordinator for execution.

Args:
    task (Task): The task to be executed.
    mode (ExecutionConfigurations): The execution mode to use for the task.

#### `.system_detail(self)`
Collects and returns details about the current state of Coordinator

#### `.shutdown(self)`
Shuts down all active execution strategies.


---
### `class TaskExecutionStrategy(ABC)`
No docstring found.

#### `.shutdown(self)`
No docstring found.

#### `.execute(self, task)`
No docstring found.


---
### `class AsyncioExecutionStrategy(TaskExecutionStrategy)`
An async-await style execution approach for tasks.

#### `.shutdown(self)`
No docstring found.

#### `.execute(self, task)`
Executes the task using asyncio.

Args:
    task (Task): The task to be executed.


---
### `class Task(Generic[_TOutput])`
A simple class used to represent a task to be completed.

#### `.__init__(self, request_id, node)`
Class constructor.

#### `.invoke(self)`
The callable that this task is representing.


---

## 3. Architectural Design

### 3.1 Coordinator and Job Management

- **Coordinator**: Acts as the invoker of tasks, managing their execution through different strategies. It maintains a state of all jobs using `CoordinatorState`.
- **Job**: Represents a unit of work with a lifecycle, including states such as "opened" and "closed".
- **CoordinatorState**: Manages the list of jobs, providing methods to add and end jobs.

### 3.2 Execution Strategies

- **TaskExecutionStrategy**: An abstract base class defining the interface for execution strategies.
- **AsyncioExecutionStrategy**: Implements an async-await style execution for tasks, leveraging Python's asyncio library.
- **ThreadedExecutionStrategy**: Extends `ConcurrentFuturesExecutor` to provide a threaded execution model (currently not fully implemented).

## 4. Important Considerations

### 4.1 Dependencies & Setup

- The component relies on the `railtracks.pubsub` module for message handling and publishing.
- Execution strategies must be provided for all configurations defined in `ExecutionConfigurations`.

### 4.2 Performance & Limitations

- The `ConcurrentFuturesExecutor` and `ProcessExecutionStrategy` are not fully implemented, limiting execution to asyncio for now.
- Ensure that tasks are idempotent and can handle retries, as execution strategies may re-invoke tasks.

## 5. Related Files

### 5.1 Code Files

- [`coordinator.py`](../packages/railtracks/src/railtracks/execution/coordinator.py): Manages task coordination and job lifecycle.
- [`execution_strategy.py`](../packages/railtracks/src/railtracks/execution/execution_strategy.py): Defines execution strategies for tasks.
- [`task.py`](../packages/railtracks/src/railtracks/execution/task.py): Represents a task to be executed.

### 5.2 Related Component Files

- [`context_management.md`](../components/context_management.md): Details on context management used within tasks.
- [`exception_handling.md`](../components/exception_handling.md): Describes exception handling mechanisms relevant to task execution.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
