# Azure AI LLM Wrapper

The Azure AI LLM Wrapper is a component designed to interface with Azure's cloud-based language models, providing a seamless integration for leveraging Azure AI's capabilities within the larger project.

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

The Azure AI LLM Wrapper is primarily used to facilitate interactions with Azure's language models. It abstracts the complexities involved in communicating with Azure AI, allowing developers to focus on building applications without worrying about the underlying API intricacies.

### 1.1 Chat with Azure AI

This use case involves sending a series of messages to an Azure AI model and receiving a response. It is crucial for applications that require natural language processing capabilities.

python
from azureai import AzureAILLM

# Initialize the Azure AI LLM with a specific model
azure_ai = AzureAILLM(model_name="text-davinci-003")

# Send a chat message
response = azure_ai.chat(messages=["Hello, how can I assist you today?"])
print(response)


### 1.2 Chat with Tools

This use case extends the basic chat functionality by allowing the integration of external tools, enhancing the model's capabilities to perform specific tasks.

python
from azureai import AzureAILLM

# Initialize the Azure AI LLM with a specific model
azure_ai = AzureAILLM(model_name="text-davinci-003")

# Define tools to be used
tools = ["calculator", "translator"]

# Send a chat message with tools
response = azure_ai.chat_with_tools(messages=["Translate 'Hello' to French."], tools=tools)
print(response)


## 2. Public API

### `class AzureAILLM(LiteLLMWrapper)`
No docstring found.

#### `.model_type(cls)`
No docstring found.

#### `.__init__(self, model_name, **kwargs)`
Initialize an Azure AI LLM instance.

Args:
    model_name (str): Name of the Azure AI model to use.
    **kwargs: Additional arguments passed to the parent LiteLLMWrapper.

Raises:
    AzureAIError: If the specified model is not available or if there are issues with the Azure AI service.

#### `.chat(self, messages, **kwargs)`
No docstring found.

#### `.chat_with_tools(self, messages, tools, **kwargs)`
No docstring found.


---

## 3. Architectural Design

### 3.1 AzureAILLM Class

- **Inheritance from LiteLLMWrapper:**
  - The `AzureAILLM` class inherits from `LiteLLMWrapper`, which provides a base implementation for language model interactions. This design choice allows for code reuse and consistency across different model wrappers.

- **Error Handling:**
  - Custom exceptions like `AzureAIError` and `FunctionCallingNotSupportedError` are used to handle specific error scenarios, ensuring that issues are communicated clearly to the developer.

- **Model Availability:**
  - The `_is_model_available` method checks if the specified model is available in Azure AI, preventing runtime errors due to unavailable models.

- **Tool Calling Support:**
  - The `_tool_calling_supported` method determines if the model supports tool calling, which is essential for integrating external functionalities.

## 4. Important Considerations

### 4.1 Dependencies & Setup

- **Logging:**
  - The component uses a custom logger obtained via `get_rt_logger(LOGGER_NAME)`. Ensure that the logging configuration is set up correctly to capture logs from this component.

- **Model Case Sensitivity:**
  - Model names are case-sensitive when matching against available Azure models. Ensure that the correct casing is used to avoid errors.

### 4.2 Performance & Limitations

- **Error Handling:**
  - The component raises `AzureAIError` for internal server errors from Azure AI, which should be handled gracefully in the application to ensure a smooth user experience.

## 5. Related Files

### 5.1 Code Files

- [`../_litellm_wrapper.py`](../_litellm_wrapper.py): Provides the base class `LiteLLMWrapper` that `AzureAILLM` extends.
- [`../_model_exception_base.py`](../_model_exception_base.py): Contains the base exception classes used for error handling in the Azure AI wrapper.

### 5.2 Related Component Files

- [`../api_provider_wrappers.md`](../api_provider_wrappers.md): Documents other API provider wrappers that integrate with different cloud services.

### 5.3 Related Feature Files

- [`../llm_integration.md`](../llm_integration.md): Describes the integration of language models within the project, including Azure AI.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.

