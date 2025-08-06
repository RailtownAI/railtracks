# LLM Node Base

The LLM Node Base component provides a foundational framework for interacting with Large Language Models (LLMs), managing message histories, and handling structured outputs. It serves as a base class for creating nodes that can communicate with LLMs, encapsulating the logic for attaching models and managing message histories.

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

The LLM Node Base component is designed to facilitate the integration and interaction with LLMs by providing a structured way to manage message histories and model interactions. It is primarily used to:

- Attach LLM models and manage message histories.
- Provide hooks for pre-processing and post-processing of messages.
- Handle structured and unstructured outputs from LLMs.

### 1.1 Attaching LLM Models

The component allows for the attachment of LLM models to nodes, enabling the processing of message histories and the execution of LLM-based tasks.

python
from railtracks.nodes.concrete._llm_base import LLMBase
from railtracks.llm import MessageHistory, ModelBase

llm_node = LLMBase(user_input=MessageHistory(), llm_model=ModelBase())


### 1.2 Managing Message Histories

The component provides mechanisms to manage and manipulate message histories, ensuring that messages are correctly formatted and processed.

python
message_history = llm_node.prepare_tool_message_history(tool_parameters={"param1": "value1"})


## 2. Public API

### `class StructuredLLM(StructuredOutputMixIn[_TOutput], LLMBase[_TOutput], ABC, Generic[_TOutput])`
No docstring found.

#### `.__init__(self, user_input, llm_model)`
Creates a new instance of the StructuredlLLM class

Args:
    user_input (MessageHistory): The message history to use for the LLM.
    llm_model (ModelBase | None, optional): The LLM model to use. Defaults to None.

#### `.name(cls)`
No docstring found.

#### `.invoke(self)`
Makes a call containing the inputted message and system prompt to the llm model and returns the response

Returns:
    (StructuredlLLM.Output): The response message from the llm model


---
### `class LLMBase(Node[_T], ABC, Generic[_T])`
A basic LLM base class that encapsulates the attaching of an LLM model and message history object.

The main functionality of the class is contained within the attachment of pre and post hooks to the model so we can
store debugging details that will allow us to determine token usage.

Args:
    user_input: The message history to use. Can be a MessageHistory object, a UserMessage object, or a string.
        If a string is provided, it will be converted to a MessageHistory with a UserMessage.
        If a UserMessage is provided, it will be converted to a MessageHistory.
        llm_model: The LLM model to use. If None, the default model will be used.

#### `.__init__(self, user_input, llm_model)`
Class constructor.

#### `.prepare_tool_message_history(cls, tool_parameters, tool_params)`
Prepare a message history for a tool call with the given parameters.

This method creates a coherent instruction message from tool parameters instead of
multiple separate messages.

Args:
    tool_parameters: Dictionary of parameter names to values
    tool_params: Iterable of Parameter objects defining the tool parameters

Returns:
    MessageHistory object with a single UserMessage containing the formatted parameters

#### `.return_output(self)`
No docstring found.

#### `.get_llm_model(cls)`
No docstring found.

#### `.system_message(cls)`
No docstring found.

#### `.return_into(self)`
Return the name of the variable to return the result into. This method can be overridden by subclasses to
customize the return variable name. By default, it returns None.

Returns
-------
str
    The name of the variable to return the result into.

#### `.format_for_return(self, result)`
Format the result for return when return_into is provided. This method can be overridden by subclasses to
customize the return format. By default, it returns None.

Args:
    result (Any): The result to format.

Returns:
    Any: The formatted result.

#### `.format_for_context(self, result)`
Format the result for context when return_into is provided. This method can be overridden by subclasses to
customize the context format. By default, it returns the result as is.

Args:
    result (Any): The result to format.

Returns:
    Any: The formatted result.

#### `.safe_copy(self)`
No docstring found.


---

## 3. Architectural Design

The LLM Node Base component is designed with flexibility and extensibility in mind, allowing developers to create custom nodes that interact with LLMs. The design focuses on:

- **Core Philosophy & Design Principles:** The component is built around the principles of modularity and reusability, allowing for easy integration with different LLM models.
- **High-Level Architecture & Data Flow:** The component manages the flow of data between the user input, message history, and the LLM model, ensuring that messages are processed and responses are handled appropriately.
- **Key Design Decisions & Trade-offs:** The component uses a hook-based system for pre-processing and post-processing messages, allowing for customization and extensibility.
- **Component Boundaries & Responsibilities:** The component is responsible for managing message histories and interacting with LLM models. It is not responsible for the implementation of specific LLM models or the handling of external dependencies.

### 3.1 Message History Management

- **Function:** `prepare_tool_message_history`
  - **Design Consideration:** Ensures that message histories are correctly formatted and processed before being sent to the LLM model.
  - **Design Consideration:** Provides a coherent instruction message from tool parameters.

## 4. Important Considerations

### 4.1 Dependencies & Setup

- The component relies on the `railtracks.llm` package for message and model management.
- Ensure that the LLM models used are compatible with the `ModelBase` class.

### 4.2 Performance & Limitations

- The component is designed to handle typical LLM interactions but may require optimization for large-scale deployments.
- Known bottlenecks include the processing of large message histories and the handling of complex model interactions.

## 5. Related Files

### 5.1 Code Files

- [`_llm_base.py`](../packages/railtracks/src/railtracks/nodes/concrete/_llm_base.py): Contains the implementation of the LLMBase class and related functionalities.
- [`structured_llm_base.py`](../packages/railtracks/src/railtracks/nodes/concrete/structured_llm_base.py): Contains the implementation of the StructuredLLM class, extending the LLMBase for structured outputs.

### 5.2 Related Component Files

- [LLM Messaging Component](../components/llm_messaging.md): Provides additional context and functionalities related to LLM messaging.

### 5.3 Related Feature Files

- [Node Management Feature](../features/node_management.md): Describes the management and orchestration of nodes within the system.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
