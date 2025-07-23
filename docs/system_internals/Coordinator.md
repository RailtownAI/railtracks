# Coordinator

## Overview

The `Coordinator` is the central component responsible for invoking and managing the execution of tasks within the Railtracks system. It acts as the concrete invoker, receiving tasks and delegating them to the appropriate execution strategies. It ensures that every task is tracked from submission to completion, maintaining a comprehensive state of all ongoing and completed jobs.

## Key Components

### `Coordinator`

This class orchestrates task execution. It maintains the system's state via `CoordinatorState`, uses different `TaskExecutionStrategy` implementations to run tasks, and listens for task completion events through the pub/sub system to keep the state up-to-date.

### `CoordinatorState`

A state container that holds a list of all `Job` objects. It tracks every task that is currently running or has been completed, providing a complete history of work handled by the `Coordinator`.

### `Job`

Represents a single unit of work. A `Job` is created when a task is submitted, and its lifecycle is tracked from an `opened` to a `closed` state. It records the task's identifiers, status, result, and timing information, offering a detailed view of each task's execution.

## Execution Flow

The execution of a task follows a well-defined sequence of events, ensuring reliable processing and state management:

1.  **Submission**: A task is submitted to the system via a call to `Coordinator.submit(task)`.
2.  **Job Creation**: The `Coordinator` immediately creates a `Job` instance for the submitted `task`. This new job is initialized with a status of `opened` and a start time.
3.  **State Update**: The newly created `Job` is added to the `CoordinatorState`, making it part of the system's tracked work.
4.  **Delegation**: The `Coordinator` determines the correct `TaskExecutionStrategy` based on the task's configuration and delegates the execution to it.
5.  **Asynchronous Execution**: The execution strategy runs the task asynchronously, allowing the `Coordinator` to manage other tasks concurrently.
6.  **Completion Notification**: Upon completion, the `TaskExecutionStrategy` publishes a `RequestCompletionMessage` to the pub/sub system.
7.  **Handling Completion**: The `Coordinator`, being a subscriber to these messages, receives the notification in its `handle_item` method.
8.  **Finalizing the Job**: The `Coordinator` finds the corresponding `Job` in its `CoordinatorState` using the `request_id` from the message and updates its status to `closed`, recording the final result and end time.

## Diagrams

### Class Diagram

This diagram illustrates the relationships between the key components involved in task execution.

```mermaid
classDiagram
    class Coordinator {
        +state: CoordinatorState
        +execution_strategy: Dict[ExecutionConfigurations, TaskExecutionStrategy]
        +submit(task: Task)
        +handle_item(message: RequestCompletionMessage)
    }
    class CoordinatorState {
        +job_list: List[Job]
        +add_job(task: Task)
        +end_job(request_id: str, result: str)
    }
    class Job {
        +request_id: str
        +status: str
        +result: str
        +start_time: float
        +end_time: float
        +create_new(task: Task) Job
        +end_job(result: str)
    }
    class Task {
        +request_id: str
        +node: object
    }
    class TaskExecutionStrategy {
        <<Interface>>
        +execute(task: Task)
    }

    Coordinator "1" *-- "1" CoordinatorState
    CoordinatorState "1" *-- "0..*" Job
    Coordinator ..> Task : uses
    Coordinator ..> TaskExecutionStrategy : uses
    Job ..> Task : created from
```

### Sequence Diagram

This diagram shows the sequence of interactions when a task is submitted and processed.

```mermaid
sequenceDiagram
    participant A as Actor
    participant C as Coordinator
    participant J as Job
    participant CS as CoordinatorState
    participant TES as TaskExecutionStrategy
    participant P as Publisher

    A->>C: submit(task)
    C->>J: create_new(task)
    J-->>C: new_job
    C->>CS: add_job(new_job)
    C->>TES: execute(task)
    
    Note over TES: Task runs asynchronously
    
    TES->>P: publish(RequestCompletionMessage)
    P->>C: handle_item(message)
    C->>CS: end_job(request_id, result)
    CS-->>C: confirmation
```
