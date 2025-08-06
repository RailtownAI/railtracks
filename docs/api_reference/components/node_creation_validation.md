# Node Creation Validation

The Node Creation Validation component provides a set of validation functions to ensure the integrity and correctness of nodes, methods, and tool metadata within the Railtracks project. This component is crucial for maintaining the robustness and reliability of the system by preventing invalid configurations and structures from being used.

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

The Node Creation Validation component is designed to validate various aspects of node creation and tool metadata. It ensures that nodes and tools are configured correctly before they are used in the system, preventing runtime errors and maintaining system integrity.

### 1.1 Validate Function

The `validate_function` use case ensures that a function is safe to use in a node by checking for any `dict` or `Dict` parameters, including nested structures. This is important to prevent unexpected behavior due to mutable data structures.

python
def example_function(param1: int, param2: dict):
    pass

try:
    validate_function(example_function)
except NodeCreationError as e:
    print(e)


### 1.2 Validate Tool Metadata

The `validate_tool_metadata` use case runs multiple checks on tool metadata, such as ensuring unique parameter names and valid system messages. This is crucial for maintaining consistent and error-free tool configurations.

python
tool_params = [{'name': 'param1'}, {'name': 'param2'}]
tool_details = {'description': 'A sample tool'}
system_message = SystemMessage(content="Sample message")

try:
    validate_tool_metadata(tool_params, tool_details, system_message, "Sample Tool")
except NodeCreationError as e:
    print(e)


## 2. Public API

### `def validate_function(func)`
Validate that the function is safe to use in a node.
If there are any dict or Dict parameters, raise an error.
Also checks recursively for any nested dictionary structures, including inside BaseModels.

Args:
    func: The function to validate.

Raises:
    NodeCreationError: If the function has dict or Dict parameters, even nested.


---
### `def check_classmethod(method, method_name)`
Ensure the given method is a classmethod.

Args:
    method: The method to check.
    method_name: The name of the method (for error messages).

Raises:
    NodeCreationError: If the method is not a classmethod.


---
### `def check_connected_nodes(node_set, node)`
Validate that node_set is non-empty and contains only subclasses of Node or functions.

Args:
    node_set: The set of nodes to check.
    node: The base Node class.

Raises:
    NodeCreationError: If node_set is empty or contains invalid types.


---
### `def check_schema(method, cls)`
Validate the output_schema returned by a classmethod.

Args:
    method: The classmethod to call.
    cls: The class to pass to the method.

Raises:
    NodeCreationError: If the output_schema is missing, invalid, or empty.


---
### `def validate_tool_metadata(tool_params, tool_details, system_message, pretty_name, max_tool_calls)`
Run all tool metadata validation checks at once.

Args:
    tool_params: The tool parameters to check.
    tool_details: The tool details object.
    system_message: The system message to check.
    pretty_name: The pretty name to check.
    max_tool_calls: The maximum number of tool calls allowed.

Raises:
    NodeCreationError: If any validation fails.


---

## 3. Architectural Design

### 3.1 Validation Strategy

- **Function Validation:** The `validate_function` method checks for the presence of `dict` or `Dict` parameters in function signatures, including nested structures. This design choice prevents the use of mutable data structures that could lead to unpredictable behavior.
  
- **Tool Metadata Validation:** The `validate_tool_metadata` function consolidates multiple validation checks into a single call, ensuring that all aspects of tool metadata are verified before use. This approach simplifies the validation process and reduces the risk of errors.

- **Class Method Checks:** The `check_classmethod` function ensures that specified methods are class methods, which is a requirement for certain operations within the system.

## 4. Important Considerations

### 4.1 Error Handling

- **NodeCreationError:** This custom exception is raised during validation failures, providing detailed error messages and notes to assist in debugging. It is defined in the [errors.py](../exceptions/errors.py) file.

- **Exception Messages:** The component uses a centralized system for managing exception messages, as defined in the [exception_messages.py](../exceptions/messages/exception_messages.py) file. This ensures consistency and ease of maintenance.

## 5. Related Files

### 5.1 Code Files

- [`validation.py`](../validation/node_creation/validation.py): Contains the implementation of the validation functions.

### 5.2 Related Component Files

- [`errors.py`](../exceptions/errors.py): Defines the `NodeCreationError` used in this component.
- [`exception_messages.py`](../exceptions/messages/exception_messages.py): Manages exception messages used throughout the component.

### 5.3 Related Feature Files

- [`validation.md`](../features/validation.md): Provides an overview of the validation feature, including its purpose and capabilities.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
