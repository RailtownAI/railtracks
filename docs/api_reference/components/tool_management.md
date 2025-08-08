# Tool Management

The Tool Management component is responsible for managing tool creation and interaction, specifically converting functions and MCP tools into callable tool instances. This component plays a crucial role in the larger project by enabling dynamic tool creation and management, which is essential for flexible and scalable system operations.

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

The Tool Management component is designed to facilitate the creation and management of tools within the system. It allows developers to convert functions and MCP tools into callable tool instances, which can then be used within the system to perform various tasks. This component is essential for enabling dynamic and flexible tool usage, which is critical for the scalability and adaptability of the system.

### 1.1 Creating a Tool from a Function

This use case involves creating a tool from a Python function. This is important for enabling the dynamic creation of tools based on existing functions, allowing for greater flexibility and reuse of code.

python
from my_project.my_component import Tool

def my_function(param1: int, param2: str) -> None:
    """Example function to be converted into a tool."""
    pass

tool_instance = Tool.from_function(my_function)


### 1.2 Creating a Tool from an MCP Tool

This use case involves creating a tool from an MCP tool object. This is important for integrating MCP tools into the system, allowing for seamless interaction and management of these tools.

python
from my_project.my_component import Tool

mcp_tool = get_mcp_tool()  # Assume this function retrieves an MCP tool
tool_instance = Tool.from_mcp(mcp_tool)


## 2. Public API



## 3. Architectural Design

The Tool Management component is designed with flexibility and scalability in mind. It provides a framework for creating and managing tools, allowing for dynamic tool creation and interaction. The component is built around the `Tool` class, which represents a single tool object with a name, description, and parameters.

### 3.1 Tool Class

- **Design Consideration:** The `Tool` class is designed to be quasi-immutable, meaning that once a tool is created, its properties cannot be changed. This ensures consistency and reliability in tool usage.
- **Design Consideration:** The `Tool` class supports the creation of tools from both functions and MCP tools, providing a unified interface for tool management.

## 4. Important Considerations

### 4.1 Parameter Handling

- The `Tool` class uses a variety of parameter handlers to manage different types of parameters, including `PydanticModelHandler`, `SequenceParameterHandler`, and `UnionParameterHandler`. These handlers ensure that parameters are correctly parsed and managed.

### 4.2 Error Handling

- The `ToolCreationError` class is used to handle errors that occur during tool creation. This class provides detailed error messages and debugging tips to assist developers in resolving issues.

## 5. Related Files

### 5.1 Code Files

- [`../packages/railtracks/src/railtracks/llm/tools/tool.py`](../packages/railtracks/src/railtracks/llm/tools/tool.py): Contains the implementation of the `Tool` class and related functionality.
- [`../packages/railtracks/src/railtracks/llm/models/_litellm_wrapper.py`](../packages/railtracks/src/railtracks/llm/models/_litellm_wrapper.py): Contains the `LiteLLMWrapper` class, which interacts with the `Tool` class for tool management.

### 5.2 Related Component Files

- [`../components/tool_parsing.md`](../components/tool_parsing.md): Provides additional documentation on tool parsing and management.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
