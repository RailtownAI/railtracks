# Tool Call Node Base

The Tool Call Node Base provides a foundational class for nodes that are capable of making tool calls, effectively managing interactions between Language Learning Models (LLMs) and tools.

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

The primary purpose of the Tool Call Node Base is to facilitate the creation and management of nodes that can make tool calls within a system that integrates LLMs. This component is crucial for enabling LLMs to interact with various tools, process responses, and manage the flow of information between the LLM and the tools.

### 1.1 Node Creation and Management

This use case involves creating nodes from tool names and arguments, ensuring that the nodes are correctly instantiated and connected.

python
node = tool_call_node_base.create_node(tool_name="example_tool", arguments={"arg1": "value1"})


### 1.2 Handling Tool Calls

This use case demonstrates how the component handles tool calls, including managing the maximum number of tool calls and processing responses.

python
await tool_call_node_base.invoke()


## 2. Public API

### `class StructuredToolCallLLM(StructuredOutputMixIn[_TBaseModel], OutputLessToolCallLLM[_TBaseModel], ABC, Generic[_TBaseModel])`
A base class for structured tool call LLMs that do not return an output.
This class is used to define the structure of the tool call and handle the
structured output.

#### `.__init__(self, user_input, llm_model, max_tool_calls)`
Class constructor.

#### `.invoke(self)`
No docstring found.


---
### `class OutputLessToolCallLLM(LLMBase[_T], ABC, Generic[_T])`
A base class that is a node which contains
 an LLm that can make tool calls. The tool calls will be returned
as calls or if there is a response, the response will be returned as an output

#### `.__init__(self, user_input, llm_model, max_tool_calls)`
Class constructor.

#### `.name(cls)`
No docstring found.

#### `.tool_nodes(cls)`
No docstring found.

#### `.create_node(self, tool_name, arguments)`
A function which creates a new instance of a node Class from a tool name and arguments.

This function may be overwritten to fit the needs of the given node as needed.

#### `.tools(self)`
No docstring found.

#### `.invoke(self)`
No docstring found.


---

## 3. Architectural Design

### 3.1 Core Design Principles

- **Node Management:** The component is designed to manage nodes that can make tool calls, ensuring that each node is correctly instantiated and connected.
- **Tool Call Handling:** The component handles tool calls by managing the flow of information between the LLM and the tools, including processing responses and managing the maximum number of tool calls.

### 3.2 High-Level Architecture

The component is structured around the `OutputLessToolCallLLM` and `StructuredToolCallLLM` classes, which provide the core functionality for managing tool calls and processing structured outputs.

- **OutputLessToolCallLLM:** This class provides the base functionality for nodes that can make tool calls without returning an output. It manages the creation of nodes, handling of tool calls, and processing of responses.
- **StructuredToolCallLLM:** This class extends the functionality of `OutputLessToolCallLLM` to handle structured outputs, ensuring that the responses are formatted according to a specified schema.

## 4. Important Considerations

### 4.1 Dependencies & Setup

- The component relies on the `railtracks` library for managing LLM interactions and tool calls.
- Ensure that the `railtracks` library is correctly installed and configured in your environment.

### 4.2 Performance & Limitations

- The component is designed to handle a limited number of tool calls, as specified by the `max_tool_calls` parameter. Exceeding this limit will result in a forced final response.

### 4.3 Debugging & Observability

- The component provides detailed error messages and warnings to assist with debugging and troubleshooting.
- Use the logging functionality provided by the `railtracks` library to monitor the flow of information and identify potential issues.

## 5. Related Files

### 5.1 Code Files

- [`../packages/railtracks/src/railtracks/nodes/concrete/_tool_call_base.py`](../packages/railtracks/src/railtracks/nodes/concrete/_tool_call_base.py): Contains the implementation of the `OutputLessToolCallLLM` class.
- [`../packages/railtracks/src/railtracks/nodes/concrete/structured_tool_call_llm_base.py`](../packages/railtracks/src/railtracks/nodes/concrete/structured_tool_call_llm_base.py): Contains the implementation of the `StructuredToolCallLLM` class.

### 5.2 Related Component Files

- [`../components/tool_management.md`](../components/tool_management.md): Documentation for the tool management component, which is closely related to the functionality provided by the Tool Call Node Base.

### 5.3 Related Feature Files

- [`../features/node_management.md`](../features/node_management.md): Documentation for the node management feature, which includes the Tool Call Node Base as a key component.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
