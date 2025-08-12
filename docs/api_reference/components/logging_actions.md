# Logging Actions

The Logging Actions component provides a framework for logging actions related to request creation and completion in a node-based system. It defines a set of classes that encapsulate different types of logging actions, such as request creation, successful completion, and failure, allowing for structured and consistent logging across the system.

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

The Logging Actions component is designed to facilitate structured logging of actions within a node-based system. It provides abstractions for logging the creation of requests, their successful completion, and any failures that occur. This component is essential for monitoring and debugging the flow of requests through the system.

### 1.1 Logging Request Creation

The `RequestCreationAction` class is used to log the creation of a request from a parent node to a child node. This is important for tracking the initiation of processes within the system.

python
from railtracks.utils.logging.action import RequestCreationAction

action = RequestCreationAction(
    parent_node_name="ParentNode",
    child_node_name="ChildNode",
    input_args=(arg1, arg2),
    input_kwargs={"key": "value"}
)
log_message = action.to_logging_msg()
print(log_message)  # Output: "ParentNode CREATED ChildNode"


### 1.2 Logging Request Completion

The `RequestSuccessAction` and `RequestFailureAction` classes are used to log the completion of requests, whether successful or failed. This is crucial for understanding the outcomes of processes and handling errors appropriately.

python
from railtracks.utils.logging.action import RequestSuccessAction, RequestFailureAction

# For a successful request
success_action = RequestSuccessAction(node_name="ChildNode", output="result")
success_log_message = success_action.to_logging_msg()
print(success_log_message)  # Output: "ChildNode DONE"

# For a failed request
failure_action = RequestFailureAction(node_name="ChildNode", exception=Exception("Error"))
failure_log_message = failure_action.to_logging_msg()
print(failure_log_message)  # Output: "ChildNode FAILED"


## 2. Public API

### `class RequestCreationAction(RTAction)`
No docstring found.

#### `.__init__(self, parent_node_name, child_node_name, input_args, input_kwargs)`
A simple object that encapsulates a Request Creation.

Args:
    parent_node_name (str): The name of the parent node that created this request.
    child_node_name (str): The name of the child node that is being created.
    input_args (Tuple[Any, ...]): The input arguments passed to the child node.
    input_kwargs (Dict[str, Any]): The input keyword arguments passed to the child node.

#### `.to_logging_msg(self)`
No docstring found.


---
### `class RequestSuccessAction(RequestCompletionBase)`
No docstring found.

#### `.__init__(self, node_name, output)`
"
A simple abstraction of a message when a request is successfully completed.

Args:
    node_name (str): The name of the child node that completed successfully.
    output (Any): The output produced by the child node.

#### `.to_logging_msg(self)`
No docstring found.


---
### `class RequestFailureAction(RequestCompletionBase)`
No docstring found.

#### `.__init__(self, node_name, exception)`
A simple abstraction of a message when a request fails.
        Args:
    node_name (str): The name of the child node that failed.
    exception (Exception): The exception that was raised during the request.

#### `.to_logging_msg(self)`
No docstring found.


---
### `def arg_kwarg_logging_str(args, kwargs)`
A helper function which converts the input args and kwargs into a string for pretty logging.


---

## 3. Architectural Design

The Logging Actions component is designed with a focus on extensibility and clarity. It uses an abstract base class `RTAction` to define a common interface for all logging actions, ensuring that each action can be converted into a log message. The component is structured to handle different stages of a request's lifecycle, from creation to completion, with specific classes for success and failure scenarios.

### 3.1 Core Design Principles

- **Abstraction and Extensibility:** The use of an abstract base class (`RTAction`) allows for easy extension of logging actions. New types of actions can be added by subclassing `RTAction` and implementing the `to_logging_msg` method.
- **Separation of Concerns:** Each class is responsible for a specific type of logging action, ensuring that the logic for creating log messages is encapsulated within the relevant class.
- **Simplicity and Clarity:** The design prioritizes simplicity, with each class having a clear and singular purpose. This makes the component easy to understand and maintain.

## 4. Important Considerations

### 4.1 Implementation Details

- **Logging Format:** The `to_logging_msg` method in each class defines the format of the log message. This format should be consistent across different actions to facilitate easy parsing and analysis of logs.
- **Error Handling:** The `RequestFailureAction` class captures exceptions that occur during request processing. It is important to ensure that exceptions are meaningful and provide enough context for debugging.

## 5. Related Files

### 5.1 Code Files

- [`action.py`](../packages/railtracks/src/railtracks/utils/logging/action.py): Contains the implementation of the Logging Actions component.

### 5.2 Related Feature Files

- [`logging_profiling.md`](../docs/features/logging_profiling.md): Provides additional context and documentation related to logging and profiling features within the system.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
