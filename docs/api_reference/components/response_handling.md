# Response Handling

The Response Handling component defines response objects for handling outputs from LLM nodes, supporting both structured and string responses. It plays a crucial role in the Railtracks system by encapsulating the outputs from LLM nodes, allowing for consistent and structured interaction management.

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

The primary purpose of the Response Handling component is to provide a standardized way to encapsulate and manage responses from LLM nodes within the Railtracks system. This component supports two main types of responses: structured and string-based, catering to different output needs of LLM nodes.

### 1.1 Handling Structured Responses

Structured responses are crucial when the output from an LLM node needs to be in a specific format or schema, often defined by a Pydantic model. This ensures that the data adheres to expected structures, facilitating easier downstream processing and validation.

python
from pydantic import BaseModel
from railtracks.llm import MessageHistory
from railtracks.nodes.concrete.response import StructuredResponse

class MyModel(BaseModel):
    field1: str
    field2: int

message_history = MessageHistory()
response = StructuredResponse(model=MyModel(field1="value", field2=42), message_history=message_history)
print(response.structured)


### 1.2 Handling String Responses

String responses are used when the output from an LLM node is a simple text string. This is useful for scenarios where the response does not need to adhere to a specific structure.

python
from railtracks.llm import MessageHistory
from railtracks.nodes.concrete.response import StringResponse

message_history = MessageHistory()
response = StringResponse(content="This is a simple string response.", message_history=message_history)
print(response.text)


## 2. Public API

### `class LLMResponse(Generic[_T])`
A special response object designed to be returned by an LLM node in the RT system.

Args:
    content: The content of the response, which can be any content of a message
    message_history: The history of messages exchanged during the interaction.

#### `.__init__(self, content, message_history)`
Class constructor.


---
### `class StructuredResponse(LLMResponse[_TBaseModel])`
A specialized response object for structured outputs from LLMs.

Args:
    model: The structured model that defines the content of the response.
    message_history: The history of messages exchanged during the interaction.

#### `.__init__(self, model, message_history)`
Class constructor.

#### `.structured(self)`
Returns the structured content of the response.


---
### `class StringResponse(LLMResponse[str])`
A specialized response object for string outputs from LLMs.

Args:
    content: The string content of the response.
    message_history: The history of messages exchanged during the interaction.

#### `.__init__(self, content, message_history)`
Class constructor.

#### `.text(self)`
Returns the text content of the response.


---

## 3. Architectural Design

The Response Handling component is designed to encapsulate the outputs from LLM nodes in a consistent manner. It leverages Python's type system and Pydantic for structured data validation, ensuring that responses are both type-safe and easy to work with.

### 3.1 Core Design Principles

- **Type Safety:** By using Python's generics and Pydantic models, the component ensures that responses are type-safe and adhere to expected schemas.
- **Flexibility:** Supports both structured and unstructured (string) responses, catering to a wide range of use cases.
- **Consistency:** Provides a unified interface for handling different types of responses, simplifying the interaction with LLM nodes.

## 4. Important Considerations

- **Dependencies:** This component relies on Pydantic for data validation and type management. Ensure that Pydantic is included in your project's dependencies.
- **Performance:** While the component is designed to be efficient, the use of Pydantic models can introduce some overhead. Consider this when working with large datasets or in performance-critical applications.
- **Security:** Ensure that any data passed to the response objects is sanitized and validated to prevent security vulnerabilities.

## 5. Related Files

### 5.1 Code Files

- [`../packages/railtracks/src/railtracks/nodes/concrete/response.py`](../packages/railtracks/src/railtracks/nodes/concrete/response.py): Defines the `LLMResponse`, `StructuredResponse`, and `StringResponse` classes.

### 5.2 Related Component Files

- [`../components/llm_node_base.md`](../components/llm_node_base.md): Provides foundational information about LLM nodes, which utilize the response handling component.

### 5.3 Related Feature Files

- [`../features/node_management.md`](../features/node_management.md): Discusses the management of nodes, including those that produce responses handled by this component.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
