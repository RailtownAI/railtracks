# Tool Callable Node

The `ToolCallable` component defines a base class for creating tool nodes that can be used with LLM (Language Model) tool calling systems. It provides a structure for defining and preparing tools that can be integrated into larger systems, particularly those involving language models.

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

The `ToolCallable` class is primarily used to define nodes that can be integrated into LLM tool calling systems. It provides a standardized way to define tool information and prepare tools with specific parameters, facilitating their use in complex workflows involving language models.

### 1.1 Defining Tool Information

The `tool_info` method is crucial for providing information about the node in the form of a tool definition. This is essential for integrating the node with LLM tool calling systems.

python
class MyToolNode(ToolCallable):
    @classmethod
    def tool_info(cls) -> Tool:
        # Implementation of tool information
        pass


### 1.2 Preparing Tools

The `prepare_tool` method allows for the creation of a new instance of the node by unpacking the tool parameters. This method can be overridden for custom behavior.

python
class MyToolNode(ToolCallable):
    @classmethod
    def prepare_tool(cls, tool_parameters: Dict[str, Any]) -> Self:
        # Custom preparation logic
        return super().prepare_tool(tool_parameters)


## 2. Public API



## 3. Architectural Design

### 3.1 Core Philosophy & Design Principles

- **Standardization:** The `ToolCallable` class provides a standardized interface for defining and preparing tools, ensuring consistency across different nodes.
- **Extensibility:** By allowing methods like `prepare_tool` to be overridden, the class supports extensibility and customization.

### 3.2 High-Level Architecture & Data Flow

The `ToolCallable` class serves as a base class, and its methods are intended to be overridden by subclasses that define specific tool nodes. The data flow involves defining tool information and preparing tools with parameters, which are then used in LLM tool calling systems.

## 4. Important Considerations

### 4.1 Dependencies & Setup

- The `ToolCallable` class relies on the `Tool` class from the `railtracks.llm` module. Ensure that this module is correctly imported and available in your environment.

### 4.2 Customization

- The `tool_info` method must be implemented in subclasses to provide specific tool information.
- The `prepare_tool` method can be overridden to customize the preparation of tool instances.

## 5. Related Files

### 5.1 Code Files

- [`tool_callable.py`](../packages/railtracks/src/railtracks/nodes/tool_callable.py): Contains the implementation of the `ToolCallable` class.

### 5.2 Related Component Files

- [Tool Call Node Base Documentation](../components/tool_call_node_base.md): Provides additional context and details about the base class for tool nodes.

### 5.3 Related Feature Files

- [Node Management Documentation](../features/node_management.md): Discusses the management and integration of nodes within the system.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
