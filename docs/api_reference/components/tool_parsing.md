# Tool Parsing

The Tool Parsing component provides utilities for parsing docstrings and handling tool parameters, supporting schema conversion and parameter handling within the larger project. It is designed to facilitate the extraction and management of parameter information from Python docstrings and JSON schemas, enabling seamless integration and interaction with various tools.

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

The Tool Parsing component is primarily used for extracting and managing parameter information from Python docstrings and JSON schemas. This is crucial for developers who need to handle tool parameters efficiently, ensuring that parameter definitions are consistent and well-documented across the project.

### 1.1 Parsing Docstring Arguments

The component can parse the 'Args:' section from a Python docstring to extract parameter names and their descriptions. This is important for generating documentation and ensuring that parameter information is easily accessible.

python
docstring = """
Parses the 'Args:' section from a docstring.
Args:
    docstring: The docstring to parse.
Returns:
    A dictionary mapping parameter names to their descriptions.
"""
parsed_args = parse_docstring_args(docstring)


### 1.2 Handling JSON Schemas

The component can parse JSON schemas into Parameter objects, which can then be used to create Pydantic models. This is important for developers who need to work with structured data and ensure that their tools are compatible with JSON schema standards.

python
json_schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer"}
    }
}
parameters = parse_json_schema_to_parameter("person", json_schema, required=True)


## 2. Public API

### `def parse_docstring_args(docstring)`
Parses the 'Args:' section from a docstring.
Returns a dictionary mapping parameter names to their descriptions.

Args:
    docstring: The docstring to parse.

Returns:
    A dictionary mapping parameter names to their descriptions.


---
### `class Parameter`
Base class for representing a tool parameter.

#### `.__init__(self, name, param_type, description, required, additional_properties, enum, default)`
Creates a new instance of a parameter object.

Args:
    name: The name of the parameter.
    param_type: The type of the parameter.
    description: A description of the parameter.
    required: Whether the parameter is required. Defaults to True.
    additional_properties: Whether to allow additional properties for object types. Defaults to False.
    enum: The enum values for the parameter.
    default: The default value for the parameter.

#### `.enum(self)`
Get the enum values for the parameter, if any.

#### `.default(self)`
Get the default value for the parameter, if any.

#### `.name(self)`
Get the name of the parameter.

#### `.param_type(self)`
Get the type of the parameter.

#### `.description(self)`
Get the description of the parameter.

#### `.required(self)`
Check if the parameter is required.

#### `.additional_properties(self)`
Check if additional properties are allowed for object types.


---
### `class ParameterHandler(ABC)`
Base abstract class for parameter handlers.

#### `.can_handle(self, param_annotation)`
Determines if this handler can process the given parameter annotation.

Args:
    param_annotation: The parameter annotation to check.

Returns:
    True if this handler can process the annotation, False otherwise.

#### `.create_parameter(self, param_name, param_annotation, description, required)`
Creates a Parameter object for the given parameter.

Args:
    param_name: The name of the parameter.
    param_annotation: The parameter's type annotation.
    description: The parameter's description.
    required: Whether the parameter is required.

Returns:
    A Parameter object representing the parameter.


---
### `def parse_json_schema_to_parameter(name, prop_schema, required)`
Given a JSON-output_schema for a property, returns a Parameter or PydanticParameter.
If prop_schema defines nested properties, this is done recursively.

Args:
    name: The name of the parameter.
    prop_schema: The JSON output_schema definition for the property.
    required: Whether the parameter is required.

Returns:
    A Parameter or PydanticParameter object representing the output_schema.


---

## 3. Architectural Design

The Tool Parsing component is designed to provide a robust and flexible framework for handling tool parameters. It leverages Python's typing and Pydantic models to ensure that parameter definitions are both type-safe and easily extensible.

### 3.1 Docstring Parsing

- **Function:** `parse_docstring_args`
  - **Design Consideration:** Utilizes regular expressions to extract parameter information from docstrings, ensuring that the parsing logic is both efficient and accurate.
  - **Design Consideration:** Handles both simple and complex parameter definitions, including those with type annotations.

### 3.2 JSON Schema Parsing

- **Function:** `parse_json_schema_to_parameter`
  - **Design Consideration:** Supports a wide range of JSON schema features, including nested objects and arrays, to ensure compatibility with complex data structures.
  - **Design Consideration:** Utilizes a modular approach, with separate functions for handling different schema constructs (e.g., `allOf`, `anyOf`).

## 4. Important Considerations

### 4.1 Dependencies & Setup

- The component relies on the `pydantic` library for handling Pydantic models. Ensure that this library is included in your `requirements.txt` file.

### 4.2 Performance & Limitations

- The docstring parsing functions use regular expressions, which can be computationally expensive for very large docstrings. Consider optimizing docstring size where possible.

### 4.3 Security Considerations

- Ensure that any input data used with this component is sanitized to prevent injection attacks, especially when parsing docstrings or JSON schemas from untrusted sources.

## 5. Related Files

### 5.1 Code Files

- [`docstring_parser.py`](../packages/railtracks/src/railtracks/llm/tools/docstring_parser.py): Contains functions for parsing Python docstrings.
- [`parameter.py`](../packages/railtracks/src/railtracks/llm/tools/parameter.py): Defines the `Parameter` class and its extensions for representing tool parameters.
- [`parameter_handlers.py`](../packages/railtracks/src/railtracks/llm/tools/parameter_handlers.py): Contains handler classes for different parameter types.
- [`schema_parser.py`](../packages/railtracks/src/railtracks/llm/tools/schema_parser.py): Provides functions for parsing JSON schemas into Parameter objects.

### 5.2 Related Feature Files

- [`tool_management.md`](../features/tool_management.md): Documents the broader tool management feature that this component is a part of.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.