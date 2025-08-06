# Exception Handling

The Exception Handling component is designed to define custom exceptions and error handling mechanisms for runtime errors, node execution, and context issues within the Railtracks project.

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

This component provides a structured way to handle exceptions that occur during the execution of nodes, context management, and other runtime operations. It ensures that errors are communicated clearly and consistently, with helpful debugging information when available.

### 1.1 Node Execution Errors

Node execution errors are critical as they can halt the entire process flow. This component provides specific exceptions like `NodeInvocationError` and `NodeCreationError` to handle such scenarios.

python
try:
    # Node execution logic
except NodeInvocationError as e:
    print(e)


### 1.2 Context Management Errors

Errors in context management can lead to incorrect data processing. The `ContextError` class is used to handle such issues.

python
try:
    # Context management logic
except ContextError as e:
    print(e)


## 2. Public API

### `class NodeInvocationError(RTError)`
Raised during node for execution problems in graph, including node or orchestration failures.
For example, bad config, missing required parameters, or structural errors.

#### `.__init__(self, message, notes, fatal)`
Class constructor.


---
### `class NodeCreationError(RTError)`
Raised during node creation/validation before any execution begins.
For example, bad config, missing required parameters, or structural errors.

#### `.__init__(self, message, notes)`
Class constructor.


---
### `class LLMError(RTError)`
Raised when an error occurs during LLM invocation or completion.

#### `.__init__(self, reason, message_history)`
Class constructor.


---
### `class GlobalTimeOutError(RTError)`
Raised on global timeout for whole execution.

#### `.__init__(self, timeout)`
Class constructor.


---
### `class ContextError(RTError)`
Raised when there is an error with the context.

#### `.__init__(self, message, notes)`
Class constructor.


---
### `class FatalError(RTError)`
No docstring found.


---

## 3. Architectural Design

The Exception Handling component is designed to provide a robust framework for managing errors across the Railtracks project. It leverages a base class, `RTError`, to ensure consistency in error reporting and handling.

### 3.1 Core Philosophy & Design Principles

- **Consistency:** All exceptions inherit from `RTError`, ensuring a uniform interface for error handling.
- **Clarity:** Error messages are color-coded for better readability in terminal outputs.
- **Extensibility:** New exceptions can be easily added by extending `RTError`.

### 3.2 High-Level Architecture & Data Flow

The component is structured into base classes and specific error classes. The base class, `RTError`, provides common functionality like color-coded messages. Specific error classes like `NodeInvocationError` and `LLMError` extend this base class to provide detailed error handling for different scenarios.

### 3.3 Key Design Decisions & Trade-offs

- **Color-Coding:** Chosen for better visibility in terminal outputs, which may not be suitable for non-terminal environments.
- **Message Externalization:** Error messages and notes are externalized in a YAML file for easy updates and localization.

## 4. Important Considerations

### 4.1 Dependencies & Setup

- **YAML Configuration:** The component relies on a YAML file (`exception_messages.yaml`) for storing error messages and notes. Ensure this file is accessible and correctly formatted.

### 4.2 Performance & Limitations

- **Terminal Output:** The color-coding feature is designed for terminal outputs and may not render correctly in other environments.

### 4.3 Debugging & Observability

- **Error Messages:** Use the `get_message` and `get_notes` functions to retrieve detailed error messages and debugging notes.

## 5. Related Files

### 5.1 Code Files

- [`_base.py`](../packages/railtracks/src/railtracks/exceptions/_base.py): Defines the base class `RTError` for all custom exceptions.
- [`errors.py`](../packages/railtracks/src/railtracks/exceptions/errors.py): Contains specific exception classes for node execution and context errors.
- [`exception_messages.py`](../packages/railtracks/src/railtracks/exceptions/messages/exception_messages.py): Manages the retrieval of error messages and notes.
- [`exception_messages.yaml`](../packages/railtracks/src/railtracks/exceptions/messages/exception_messages.yaml): Stores error messages and notes in a structured format.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
