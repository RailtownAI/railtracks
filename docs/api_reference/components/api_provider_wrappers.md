# API Provider Wrappers

The API Provider Wrappers component provides a unified interface for interacting with different language model providers. It ensures compatibility and error handling for model interactions, abstracting the complexities of each provider's API.

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

The primary purpose of the API Provider Wrappers is to facilitate seamless interaction with various language model providers such as Anthropic, Gemini, and OpenAI. This component abstracts the provider-specific details and provides a consistent interface for model operations.

### 1.1 Interacting with a Model

This use case demonstrates how to initialize a model wrapper and perform operations such as sending messages to the model.

python
from railtracks.llm.models.api_providers.openai import OpenAILLM

# Initialize the OpenAI model wrapper
model = OpenAILLM(model_name="gpt-3.5-turbo")

# Interact with the model
response = model.chat_with_tools(messages=["Hello, how are you?"], tools=[])
print(response)


### 1.2 Handling Model Errors

This use case shows how to handle errors when interacting with a model, such as when a model is not found.

python
from railtracks.llm.models.api_providers.openai import OpenAILLM
from railtracks.llm.models.api_providers._provider_wrapper import ModelNotFoundError

try:
    model = OpenAILLM(model_name="nonexistent-model")
except ModelNotFoundError as e:
    print(f"Error: {e}")


## 2. Public API



## 3. Architectural Design

The API Provider Wrappers component is designed to abstract the complexities of interacting with different language model providers. It uses a base class, `ProviderLLMWrapper`, which defines the common interface and behavior for all provider-specific wrappers.

### 3.1 ProviderLLMWrapper

- **Design Consideration:** The `ProviderLLMWrapper` class inherits from `LiteLLMWrapper` and `ABC` (Abstract Base Class), ensuring that all provider-specific wrappers implement the `model_type` method.
- **Logic Flow:** The constructor verifies the model's provider using `get_llm_provider` and raises a `ModelNotFoundError` if the model is not recognized.
- **Trade-offs:** The design prioritizes a consistent interface over provider-specific optimizations, which may lead to some performance overhead.

### 3.2 Provider-Specific Wrappers

- **AnthropicLLM:** Implements the `model_type` method to return "Anthropic".
- **GeminiLLM:** Overrides `full_model_name` to accommodate the "gemini/{model_name}" format.
- **OpenAILLM:** Provides access to the OpenAI API and implements the `model_type` method to return "OpenAI".

## 4. Important Considerations

### 4.1 Error Handling

- **ModelNotFoundError:** Raised when a model is not found. It includes helpful debugging notes.
- **FunctionCallingNotSupportedError:** Raised if the model does not support function calling.

### 4.2 Dependencies

- **litellm:** The component relies on the `litellm` library for provider logic and function calling support.

## 5. Related Files

### 5.1 Code Files

- [`_provider_wrapper.py`](../packages/railtracks/src/railtracks/llm/models/api_providers/_provider_wrapper.py): Contains the base class for provider wrappers.
- [`anthropic.py`](../packages/railtracks/src/railtracks/llm/models/api_providers/anthropic.py): Implements the Anthropic provider wrapper.
- [`gemini.py`](../packages/railtracks/src/railtracks/llm/models/api_providers/gemini.py): Implements the Gemini provider wrapper.
- [`openai.py`](../packages/railtracks/src/railtracks/llm/models/api_providers/openai.py): Implements the OpenAI provider wrapper.

### 5.2 Related Component Files

- [`model_interaction.md`](../components/model_interaction.md): Details on how models interact within the system.
- [`model_error_handling.md`](../components/model_error_handling.md): Describes error handling strategies for model interactions.

### 5.3 Related Feature Files

- [`llm_integration.md`](../features/llm_integration.md): Discusses the integration of language models into the broader system.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
