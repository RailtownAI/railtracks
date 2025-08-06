# LLM Messaging

The LLM Messaging component is designed to handle messaging for language models, including managing message history, content, and structured interactions.

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

The LLM Messaging component is essential for managing interactions with language models. It provides structures for message content, maintains message history, and supports different roles in messaging, such as user, assistant, system, and tool. This component is crucial for applications that require structured communication with language models.

### 1.1 Message Creation and Management

This use case involves creating and managing messages with different roles and content types.

python
from railtracks.llm.message import UserMessage, SystemMessage, AssistantMessage, ToolMessage
from railtracks.llm.content import ToolResponse

# Create a user message
user_msg = UserMessage(content="Hello, how can I assist you today?")

# Create a system message
system_msg = SystemMessage(content="System maintenance scheduled at midnight.")

# Create an assistant message
assistant_msg = AssistantMessage(content="Sure, I can help with that.")

# Create a tool message with a tool response
tool_response = ToolResponse(identifier="123", name="WeatherTool", result="Sunny")
tool_msg = ToolMessage(content=tool_response)


### 1.2 Message History Management

This use case demonstrates how to manage and manipulate message history.

python
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import UserMessage, SystemMessage

# Create a message history
history = MessageHistory()

# Append messages to history
history.append(UserMessage(content="User message"))
history.append(SystemMessage(content="System message"))

# Remove system messages from history
filtered_history = history.removed_system_messages()


## 2. Public API

### `class ToolCall(BaseModel)`
A simple model object that represents a tool call.

This simple model represents a moment when a tool is called.


---
### `class ToolResponse(BaseModel)`
A simple model object that represents a tool response.

This simple model should be used when adding a response to a tool.


---
### `class MessageHistory(List[Message])`
A basic object that represents a history of messages. The object has all the same capability as a list such as
`.remove()`, `.append()`, etc.

#### `.removed_system_messages(self)`
Returns a new MessageHistory object with all SystemMessages removed.


---
### `class UserMessage(_StringOnlyContent)`
Note that we only support string input

Args:
    content (str): The content of the user message.
    inject_prompt (bool, optional): Whether to inject prompt with context variables. Defaults to True.

#### `.__init__(self, content, inject_prompt)`
Class constructor.


---
### `class SystemMessage(_StringOnlyContent)`
A simple class that represents a system message.

Args:
    content (str): The content of the system message.
    inject_prompt (bool, optional): Whether to inject prompt with context  variables. Defaults to True.

#### `.__init__(self, content, inject_prompt)`
Class constructor.


---
### `class AssistantMessage(Message[_T], Generic[_T])`
A simple class that represents a message from the assistant.

Args:
    content (_T): The content of the assistant message.
    inject_prompt (bool, optional): Whether to inject prompt with context  variables. Defaults to True.

#### `.__init__(self, content, inject_prompt)`
Class constructor.


---
### `class ToolMessage(Message[ToolResponse])`
A simple class that represents a message that is a tool call answer.

Args:
    content (ToolResponse): The tool response content for the message.

#### `.__init__(self, content)`
Class constructor.


---

## 3. Architectural Design

### 3.1 Message Structure and Roles

- **Message Class**: The `Message` class is a generic base class that represents a message with content and a role. It supports various content types, including strings, tool calls, and tool responses.
- **Role Enum**: The `Role` enum defines the possible roles a message can have, such as `assistant`, `user`, `system`, and `tool`.
- **Design Considerations**: The design allows for flexibility in message content and role assignment, supporting diverse interaction scenarios with language models.

### 3.2 Content Management

- **ToolCall and ToolResponse**: These classes represent tool interactions, encapsulating the call and response data. They are used to structure messages that involve tool operations.
- **Content Union**: The `Content` type is a union of possible content types, ensuring that messages can handle various data structures.

### 3.3 Message History

- **MessageHistory Class**: Inherits from Python's list to manage a sequence of messages. It provides additional functionality, such as filtering out system messages.
- **Design Considerations**: The use of list inheritance allows for natural list operations while extending functionality specific to message history management.

## 4. Important Considerations

### 4.1 Content Validation

- **Content Validation**: The `Message` class includes a `validate_content` method to ensure that the content type is appropriate for the message type. This is crucial for maintaining data integrity.

### 4.2 Role Assignment

- **Role Assignment**: The role of a message is critical for its processing and interpretation. Ensure that roles are correctly assigned to avoid miscommunication in interactions.

## 5. Related Files

### 5.1 Code Files

- [`content.py`](../packages/railtracks/src/railtracks/llm/content.py): Defines data structures for tool calls and responses.
- [`history.py`](../packages/railtracks/src/railtracks/llm/history.py): Manages message history, including filtering capabilities.
- [`message.py`](../packages/railtracks/src/railtracks/llm/message.py): Contains the core message classes and role definitions.

### 5.2 Related Feature Files

- [`llm_integration.md`](../features/llm_integration.md): Documents the integration of LLM messaging within the broader system.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
