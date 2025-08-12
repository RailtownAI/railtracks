# Model Interaction

The Model Interaction component defines interfaces and hooks for interacting with models, supporting chat, structured interactions, and streaming. It provides a flexible framework for integrating various model types and handling interactions in a structured manner.

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

The Model Interaction component is designed to facilitate communication with language models through various interaction types such as chat, structured interactions, and streaming. It allows developers to insert hooks for pre-processing messages, post-processing responses, and handling exceptions, providing a customizable and extensible interface for model interactions.

### 1.1 Chat Interaction

Chat interaction allows for real-time communication with a model using a sequence of messages.

python
from railtracks.llm.model import ModelBase
from railtracks.llm.history import MessageHistory

class MyModel(ModelBase):
    def model_name(self) -> str:
        return "MyModel"

    @classmethod
    def model_type(cls) -> str:
        return "CustomModel"

    def _chat(self, messages: MessageHistory, **kwargs):
        # Implement chat logic here
        pass

# Usage
model = MyModel()
response = model.chat(messages=MessageHistory())


### 1.2 Structured Interaction

Structured interaction involves using a predefined schema to interact with the model, ensuring that the output adheres to a specific format.

python
from pydantic import BaseModel

class OutputSchema(BaseModel):
    field1: str
    field2: int

response = model.structured(messages=MessageHistory(), schema=OutputSchema)


## 2. Public API

### `class ModelBase(ABC)`
A simple base that represents the behavior of a model that can be used for chat, structured interactions, and streaming.

The base class allows for the insertion of hooks that can modify the messages before they are sent to the model,
response after they are received, and map exceptions that may occur during the interaction.

All the hooks are optional and can be added or removed as needed.

#### `.__init__(self, pre_hook, post_hook, exception_hook)`
Class constructor.

#### `.add_pre_hook(self, hook)`
Adds a pre-hook to modify messages before sending them to the model.

#### `.add_post_hook(self, hook)`
Adds a post-hook to modify the response after receiving it from the model.

#### `.add_exception_hook(self, hook)`
Adds an exception hook to handle exceptions during model interactions.

#### `.remove_pre_hooks(self)`
Removes all of the hooks that modify messages before sending them to the model.

#### `.remove_post_hooks(self)`
Removes all of the hooks that modify the response after receiving it from the model.

#### `.remove_exception_hooks(self)`
Removes all of the hooks that handle exceptions during model interactions.

#### `.model_name(self)`
Returns the name of the model being used.

It can be treated as unique identifier for the model when paired with the `model_type`.

#### `.model_type(cls)`
The name of the provider of this model or the model type.

#### `.chat(self, messages, **kwargs)`
Chat with the model using the provided messages.

#### `.achat(self, messages, **kwargs)`
Asynchronous chat with the model using the provided messages.

#### `.structured(self, messages, schema, **kwargs)`
Structured interaction with the model using the provided messages and output_schema.

#### `.astructured(self, messages, schema, **kwargs)`
Asynchronous structured interaction with the model using the provided messages and output_schema.

#### `.stream_chat(self, messages, **kwargs)`
Stream chat with the model using the provided messages.

#### `.astream_chat(self, messages, **kwargs)`
Asynchronous stream chat with the model using the provided messages.

#### `.chat_with_tools(self, messages, tools, **kwargs)`
Chat with the model using the provided messages and tools.

#### `.achat_with_tools(self, messages, tools, **kwargs)`
Asynchronous chat with the model using the provided messages and tools.


---
### `class Response`
A simple object that represents a response from a model. It includes specific detail about the returned message
and any other additional information from the model.

#### `.__init__(self, message, streamer, message_info)`
Creates a new instance of a response object.

Args:
    message: The message that was returned as part of this.
    streamer: A generator that streams the response as a collection of chunked strings.
    message_info: Additional information about the message, such as input/output tokens and latency.

#### `.message(self)`
Gets the message that was returned as part of this response.

If none exists, this will return None.

#### `.streamer(self)`
Gets the streamer that was returned as part of this response.

This object will only be filled in the case when you asked for a streamed response.

If none exists, this will return None.

#### `.message_info(self)`
Gets the message info that was returned as part of this response.

This object contains additional information about the message, such as input/output tokens and latency.


---
### `class TypeMapper`
A simple type that will provide functionality to convert a dictionary representation of kwargs into the appropriate
types based on the function signature

Use the method `convert_kwargs_to_appropriate_types` to convert the kwargs dictionary.

#### `.__init__(self, function)`
Class constructor.

#### `.convert_kwargs_to_appropriate_types(self, kwargs)`
Convert kwargs to appropriate types based on function signature.


---

## 3. Architectural Design

The Model Interaction component is built around the `ModelBase` class, which serves as an abstract base class for implementing various model interaction types. It provides methods for synchronous and asynchronous interactions, including chat, structured interactions, and streaming.

### 3.1 Core Philosophy & Design Principles

- **Extensibility:** The component is designed to be easily extended with custom models by subclassing `ModelBase`.
- **Hook Mechanism:** Pre-hooks, post-hooks, and exception hooks allow for flexible customization of the interaction process.

### 3.2 High-Level Architecture & Data Flow

The component uses a hook-based architecture to process messages and responses. Hooks can be added or removed dynamically, allowing for pre-processing of messages, post-processing of responses, and handling of exceptions.

### 3.3 Key Design Decisions & Trade-offs

- **Hook Flexibility:** The use of hooks provides flexibility but may introduce complexity in managing the order and interaction of hooks.
- **Abstract Methods:** The use of abstract methods in `ModelBase` enforces implementation of core interaction logic in subclasses.

## 4. Important Considerations

### 4.1 Dependencies & Setup

- **Pydantic:** Used for schema validation in structured interactions.
- **MessageHistory:** Custom object representing the sequence of messages in an interaction.

### 4.2 Performance & Limitations

- **Concurrency:** Asynchronous methods are provided for non-blocking interactions, but care must be taken to manage concurrency and state.

## 5. Related Files

### 5.1 Code Files

- [`model.py`](../packages/railtracks/src/railtracks/llm/model.py): Defines the `ModelBase` class and interaction methods.
- [`response.py`](../packages/railtracks/src/railtracks/llm/response.py): Defines the `Response` class for handling model responses.
- [`type_mapping.py`](../packages/railtracks/src/railtracks/llm/type_mapping.py): Provides functionality for converting dictionary representations to appropriate types.

### 5.2 Related Component Files

- [`llm_messaging.md`](../components/llm_messaging.md): Documentation for the messaging component related to model interactions.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
