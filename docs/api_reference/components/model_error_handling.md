# Model Error Handling

This component defines custom error classes for handling exceptions related to language models, including unsupported features.

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

The primary purpose of this component is to provide a structured way to handle errors specific to Large Language Models (LLMs). It includes custom exceptions that can be used to signal specific issues, such as unsupported features, in a clear and consistent manner.

### 1.1 Handling General Model Errors

The `ModelError` class is used to represent any error related to LLMs. It provides a mechanism to include a reason for the error and optionally, a history of messages leading up to the error.

python
from railtracks.llm.models._model_exception_base import ModelError
from railtracks.llm.history import MessageHistory

# Example usage
try:
    raise ModelError("An unexpected error occurred", MessageHistory())
except ModelError as e:
    print(e)


### 1.2 Handling Unsupported Function Calling

The `FunctionCallingNotSupportedError` is a specific type of `ModelError` that is raised when a model does not support function calling, which is crucial for certain operations.

python
from railtracks.llm.models._model_exception_base import FunctionCallingNotSupportedError

# Example usage
try:
    raise FunctionCallingNotSupportedError("ExampleModel")
except FunctionCallingNotSupportedError as e:
    print(e)


## 2. Public API

### `class ModelError(RTLLMError)`
Any Large Language Model (LLM) error.

#### `.__init__(self, reason, message_history)`
Class constructor.


---
### `class FunctionCallingNotSupportedError(ModelError)`
Error raised when a model does not support function calling.

#### `.__init__(self, model_name)`
Class constructor.


---

## 3. Architectural Design

### 3.1 Error Handling Design

- **ModelError Class:**
  - Inherits from `RTLLMError`, a base class for all LLM-related exceptions.
  - Designed to encapsulate a reason for the error and optionally, a `MessageHistory` object.
  - Utilizes ANSI color codes for enhanced terminal output readability.

- **FunctionCallingNotSupportedError Class:**
  - Inherits from `ModelError`.
  - Specifically used to indicate that a model does not support function calling.
  - Provides a clear error message indicating the model's limitation.

## 4. Important Considerations

### 4.1 Implementation Details

- **Colorized Output:**
  - The `RTLLMError` class provides a `_color` method to apply ANSI color codes to text, enhancing readability in terminal outputs.

- **Message History:**
  - The `MessageHistory` class, which is a list of `Message` objects, can be used to track the sequence of messages leading to an error. This is useful for debugging and understanding the context of errors.

## 5. Related Files

### 5.1 Code Files

- [`../_model_exception_base.py`](../_model_exception_base.py): Defines the `ModelError` and `FunctionCallingNotSupportedError` classes.
- [`../_exception_base.py`](../_exception_base.py): Contains the `RTLLMError` base class, which provides foundational error handling capabilities.
- [`../history.py`](../history.py): Implements the `MessageHistory` class, used for tracking message sequences.

### 5.2 Related Component Files

- [`../components/exception_handling.md`](../components/exception_handling.md): Provides broader context on exception handling strategies within the project.

### 5.3 Related Feature Files

- [`../features/llm_integration.md`](../features/llm_integration.md): Discusses the integration of LLMs and how error handling is applied in that context.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
