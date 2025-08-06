# Session Management

The `Session` component is a crucial part of the Railtracks framework, responsible for managing execution sessions. It sets up essential components like the coordinator and publisher, ensuring seamless execution of tasks within the system.

**Version:** 0.0.1

**Component Contact:** @railtracks_dev

## Table of Contents

- [1. Purpose](#1-purpose)
- [2. Public API](#2-public-api)
- [3. Architectural Design](#3-architectural-design)
- [4. Important Considerations](#4-important-considerations)
- [5. Related Files](#5-related-files)
- [CHANGELOG](#changelog)

## 1. Purpose

The `Session` component is designed to manage the lifecycle of execution sessions in the Railtracks framework. It initializes and configures all necessary components, such as the coordinator and publisher, to facilitate task execution. The `Session` also handles context management, logging, and state persistence, providing a comprehensive environment for running workflows.

### 1.1 Session Initialization and Execution

The primary use case for the `Session` component is to initialize and manage the execution of tasks within a session. This involves setting up the necessary components and executing tasks in a controlled environment.

python
import railtracks as rt

with rt.Session() as run:
    result = rt.call_sync(rt.nodes.NodeA, "Hello World")


### 1.2 Context and State Management

Another critical use case is managing the context and state of the execution session. The `Session` ensures that global context variables are correctly registered and cleaned up, and it saves the execution state to a file if configured to do so.

python
session = rt.Session(context={"key": "value"}, save_state=True)


## 2. Public API

### `class Session`
The main class for managing an execution session.

This class is responsible for setting up all the necessary components for running a Railtracks execution, including the coordinator, publisher, and state management.

For the configuration parameters of the setting. It will follow this precedence:
1. The parameters in the `Session` constructor.
2. The parameters in global context variables.
3. The default values.

Default Values:
- `timeout`: 150.0 seconds
- `end_on_error`: False
- `logging_setting`: "REGULAR"
- `log_file`: None (logs will not be written to a file)
- `broadcast_callback`: None (no callback for broadcast messages)
- `run_identifier`: None (a random identifier will be generated)
- `prompt_injection`: True (the prompt will be automatically injected from context variables)
- `save_state`: True (the state of the execution will be saved to a file at the end of the run in the `.railtracks` directory)


Args:
    context (Dict[str, Any], optional): A dictionary of global context variables to be used during the execution.
    timeout (float, optional): The maximum number of seconds to wait for a response to your top-level request.
    end_on_error (bool, optional): If True, the execution will stop when an exception is encountered.
    logging_setting (allowable_log_levels, optional): The setting for the level of logging you would like to have.
    log_file (str | os.PathLike | None, optional): The file to which the logs will be written.
    broadcast_callback (Callable[[str], None] | Callable[[str], Coroutine[None, None, None]] | None, optional): A callback function that will be called with the broadcast messages.
    run_identifier (str | None, optional): A unique identifier for the run.
    prompt_injection (bool, optional): If True, the prompt will be automatically injected from context variables.
    save_state (bool, optional): If True, the state of the execution will be saved to a file at the end of the run in the `.railtracks` directory.

Example Usage:
python
import railtracks as rt

with rt.Session() as run:
    result = rt.call_sync(rt.nodes.NodeA, "Hello World")


#### `.__init__(self, context)`
Class constructor.

#### `.global_config_precedence(cls, timeout, end_on_error, logging_setting, log_file, broadcast_callback, run_identifier, prompt_injection, save_state)`
Uses the following precedence order to determine the configuration parameters:
1. The parameters in the method parameters.
2. The parameters in global context variables.
3. The default values.

#### `.info(self)`
Returns the current state of the runner.

This is useful for debugging and viewing the current state of the run.


---

## 3. Architectural Design

The `Session` component is designed to provide a unified interface for managing execution sessions. It integrates various subsystems, such as the coordinator, publisher, and state management, into a cohesive unit.

### 3.1 Core Philosophy & Design Principles

- **Modularity:** The `Session` encapsulates all necessary components, allowing for easy management and extension.
- **Flexibility:** Configuration options are provided to customize the session's behavior, such as logging settings and error handling.
- **Robustness:** The `Session` ensures proper initialization and cleanup of resources, preventing resource leaks and ensuring consistent execution.

### 3.2 High-Level Architecture & Data Flow

The `Session` initializes the `Coordinator`, `RTPublisher`, and `RTState`, setting up the necessary infrastructure for task execution. It manages the flow of data and control through these components, coordinating task execution and handling completion messages.

### 3.3 Key Design Decisions & Trade-offs

- **Asynchronous Execution:** The use of `AsyncioExecutionStrategy` allows for efficient task execution, but requires careful management of asynchronous operations.
- **State Persistence:** Saving the execution state to a file provides valuable debugging information, but may introduce performance overhead.

## 4. Important Considerations

### 4.1 Dependencies & Setup

- **Environment Variables:** Ensure that any required environment variables are set before initializing a `Session`.
- **Configuration Files:** The `Session` relies on configuration files for logging and execution settings.

### 4.2 Performance & Limitations

- **Concurrency:** The `Session` supports concurrent task execution, but care must be taken to avoid race conditions.
- **Resource Usage:** Monitor memory and CPU usage, especially when handling large datasets or complex workflows.

## 5. Related Files

### 5.1 Code Files

- [`session.py`](../packages/railtracks/src/railtracks/session.py): Contains the implementation of the `Session` class.

### 5.2 Related Component Files

- [`task_execution.md`](../components/task_execution.md): Details the task execution process and its integration with the `Session`.
- [`pubsub_messaging.md`](../components/pubsub_messaging.md): Describes the pub/sub messaging system used by the `Session`.

### 5.3 Related Feature Files

- [`task_execution.md`](../features/task_execution.md): Provides an overview of task execution features and their relationship with the `Session`.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
