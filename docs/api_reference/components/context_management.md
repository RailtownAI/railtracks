# Context Management

The Context Management component is responsible for managing context variables and configurations within a thread or execution environment, providing utilities for context-specific data handling.

**Version:** 0.0.1

**Component Contact:** @developer_username

## Table of Contents

- [1. Purpose](#1-purpose)
- [2. Public API](#2-public-api)
- [3. Architectural Design](#3-architectural-design)
- [4. Important Considerations](#4-important-considerations)
- [5. Related Files](#5-related-files)
- [CHANGELOG](#changelog)

## 1. Purpose

The Context Management component is designed to handle context variables and configurations within a thread or execution environment. It provides utilities for managing context-specific data, ensuring that each thread or execution environment can maintain its own set of context variables without interference from others.

### 1.1 Context Variable Management

This use case involves managing context variables that are scoped within the context of a single runner. It is crucial for maintaining thread-specific data integrity.

python
from railtracks.context.central import register_globals, get_runner_id

# Register global variables for the current thread
register_globals(
    runner_id="runner_123",
    rt_publisher=None,
    parent_id=None,
    executor_config=ExecutorConfig(),
    global_context_vars={}
)

# Retrieve the runner ID for the current thread
runner_id = get_runner_id()
print(runner_id)  # Output: runner_123


### 1.2 Executor Configuration Management

This use case demonstrates how to manage executor configurations within the context, allowing for customization of execution behavior.

python
from railtracks.context.central import set_global_config, get_global_config

# Set a new global executor configuration
set_global_config(ExecutorConfig(timeout=200.0, end_on_error=True))

# Retrieve the current global executor configuration
config = get_global_config()
print(config.timeout)  # Output: 200.0


## 2. Public API

### `def safe_get_runner_context()`
Safely get the runner context for the current thread.

    Returns:
        RunnerContextVars: The runner context associated with the current thread.

    Raises:
        RuntimeError: If the global variables have not been registered.


---
### `def is_context_present()`
Returns true if a context exists.


---
### `def is_context_active()`
Check if the global variables for the current thread are active.

Returns:
    bool: True if the global variables are active, False otherwise.


---
### `def get_publisher()`
Get the publisher for the current thread's global variables.

Returns:
    RTPublisher: The publisher associated with the current thread's global variables.

Raises:
    RuntimeError: If the global variables have not been registered.


---
### `def get_runner_id()`
Get the runner ID of the current thread's global variables.

Returns:
    str: The runner ID associated with the current thread's global variables.

Raises:
    RuntimeError: If the global variables have not been registered.


---
### `def get_parent_id()`
Get the parent ID of the current thread's global variables.

Returns:
    str | None: The parent ID associated with the current thread's global variables, or None if not set.

Raises:
    RuntimeError: If the global variables have not been registered.


---
### `def register_globals()`
Register the global variables for the current thread.


---
### `def activate_publisher()`
Activate the publisher for the current thread's global variables.

This function should be called to ensure that the publisher is running and can be used to publish messages.


---
### `def shutdown_publisher()`
Shutdown the publisher for the current thread's global variables.

This function should be called to stop the publisher and clean up resources.


---
### `def get_global_config()`
Get the executor configuration for the current thread's global variables.

Returns:
    ExecutorConfig: The executor configuration associated with the current thread's global variables, or None if not set.


---
### `def set_local_config(executor_config)`
Set the executor configuration for the current thread's global variables.

Args:
    executor_config (ExecutorConfig): The executor configuration to set.


---
### `def set_global_config(executor_config)`
Set the executor configuration for the current thread's global variables.

Args:
    executor_config (ExecutorConfig): The executor configuration to set.


---
### `def update_parent_id(new_parent_id)`
Update the parent ID of the current thread's global variables.


---
### `def delete_globals()`
Resets the globals to None.


---
### `def get(default)`
Get a value from context

Args:
    key (str): The key to retrieve.
    default (Any | None): The default value to return if the key does not exist. If set to None and the key does not exist, a KeyError will be raised.
Returns:
    Any: The value associated with the key, or the default value if the key does not exist.

Raises:
    KeyError: If the key does not exist and no default value is provided.


---
### `def put(key, value)`
Set a value in the context.

Args:
    key (str): The key to set.
    value (Any): The value to set.


---
### `def update(data)`
Sets the values in the context. If the context already has values, this will overwrite them, but it will not delete any existing keys.

Args:
    data (dict[str, Any]): The data to update the context with.


---
### `def delete(key)`
Delete a key from the context.

Args:
    key (str): The key to delete.

Raises:
    KeyError: If the key does not exist.


---
### `def set_config()`
Sets the global configuration for the executor. This will be propagated to all new runners created after this call.

- If you call this function after the runner has been created, it will not affect the current runner.
- This function will only overwrite the values that are provided, leaving the rest unchanged.


---

## 3. Architectural Design

### 3.1 Context Management Design

- **Core Philosophy & Design Principles:** The component is designed around the principle of thread-local storage, ensuring that each thread or execution environment can maintain its own set of context variables.
- **High-Level Architecture & Data Flow:** The component uses Python's `contextvars` to manage context variables. The `RunnerContextVars` class encapsulates the context for a single runner, including internal and external contexts.
- **Key Design Decisions & Trade-offs:** The use of `contextvars` allows for efficient context management without the overhead of manual context passing. However, it requires careful management of context activation and deactivation.
- **Component Boundaries & Responsibilities:** This component is responsible for managing context variables and executor configurations. It is not responsible for the actual execution of tasks or handling of messages.
- **Rejected Alternatives:** Using global variables was considered but rejected due to potential conflicts in multi-threaded environments.

## 4. Important Considerations

### 4.1 Context Activation and Deactivation

- **Dependencies & Setup:** The component relies on `contextvars` for managing context variables. Ensure that the `contextvars` module is available in your Python environment.
- **Performance & Limitations:** The component is designed for use in multi-threaded environments. It may not perform optimally in single-threaded applications.
- **State Management & Concurrency:** The component is thread-safe, but care must be taken to activate and deactivate contexts correctly to avoid data leakage between threads.
- **Security Considerations:** Ensure that context variables do not contain sensitive information that could be exposed through logging or debugging.
- **Configuration & Feature Flags:** The component supports configuration through the `ExecutorConfig` class, allowing for customization of execution behavior.

## 5. Related Files

### 5.1 Code Files

- [`central.py`](../packages/railtracks/src/railtracks/context/central.py): Contains the main logic for managing context variables and configurations.
- [`external.py`](../packages/railtracks/src/railtracks/context/external.py): Defines the `ExternalContext` and `MutableExternalContext` classes for managing external context variables.
- [`internal.py`](../packages/railtracks/src/railtracks/context/internal.py): Defines the `InternalContext` class for managing internal context variables.

### 5.2 Related Component Files

- [`../utils/config.py`](../packages/railtracks/src/railtracks/utils/config.py): Contains the `ExecutorConfig` class used for managing executor configurations.

### 5.3 Related Feature Files

- [`../features/context_management.md`](../features/context_management.md): Documentation for the Context Management feature.

### 5.4 External Dependencies

- [`https://docs.python.org/3/library/contextvars.html`](https://docs.python.org/3/library/contextvars.html): Python's `contextvars` module documentation.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
