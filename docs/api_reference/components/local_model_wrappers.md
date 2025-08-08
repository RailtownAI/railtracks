# Local Model Wrappers

The Local Model Wrappers component provides a wrapper for local language model interactions, specifically designed for Ollama server models. It facilitates seamless communication with local instances of language models hosted on an Ollama server, ensuring efficient and reliable model utilization.

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

The Local Model Wrappers component is primarily used to interact with language models hosted on a local Ollama server. It abstracts the complexities involved in setting up and managing connections to the server, allowing developers to focus on model interactions.

### 1.1 Initialize Ollama Model

The primary use case is to initialize a connection to an Ollama model hosted locally. This is crucial for applications that require local processing of language models without relying on cloud services.

python
from railtracks.llm.models.local.ollama import OllamaLLM

ollama_model = OllamaLLM(model_name="my_model", domain="default")


### 1.2 Chat with Tools

Another use case is to facilitate conversations with the model using tools, which is essential for applications that require interactive model responses.

python
response = ollama_model.chat_with_tools(messages=["Hello, model!"], tools=my_tools)


## 2. Public API

### `class OllamaLLM(LiteLLMWrapper)`
No docstring found.

#### `.__init__(self, model_name, domain, custom_domain, **kwargs)`
Initialize an Ollama LLM instance.

Args:
    model_name (str): Name of the Ollama model to use.
    domain (Literal["default", "auto", "custom"], optional): The domain configuration mode.
        - "default": Uses the default localhost domain (http://localhost:11434)
        - "auto": Uses the OLLAMA_HOST environment variable, raises OllamaError if not set
        - "custom": Uses the provided custom_domain parameter, raises OllamaError if not provided
        Defaults to "default".
    custom_domain (str | None, optional): Custom domain URL to use when domain is set to "custom".
        Must be provided if domain="custom". Defaults to None.
    **kwargs: Additional arguments passed to the parent LiteLLMWrapper.

Raises:
    OllamaError: If:
        - domain is "auto" and OLLAMA_HOST environment variable is not set
        - domain is "custom" and custom_domain is not provided
        - specified model is not available on the server
    RequestException: If connection to Ollama server fails

#### `.chat_with_tools(self, messages, tools, **kwargs)`
No docstring found.

#### `.model_type(cls)`
No docstring found.


---

## 3. Architectural Design

The design of the Local Model Wrappers component is centered around providing a robust and flexible interface for interacting with local language models.

### 3.1 OllamaLLM Class

- **Domain Configuration:** The `OllamaLLM` class allows for flexible domain configuration through the `domain` parameter, supporting "default", "auto", and "custom" modes.
- **Error Handling:** The component includes comprehensive error handling, raising `OllamaError` for domain configuration issues and `requests.exceptions.RequestException` for server connection failures.
- **Logging:** Utilizes a dedicated logger (`OLLAMA`) to track critical operations and errors, aiding in debugging and monitoring.

## 4. Important Considerations

### 4.1 Dependencies & Setup

- **Environment Variables:** The `OLLAMA_HOST` environment variable must be set when using the "auto" domain configuration.
- **Server Availability:** The Ollama server must be running and accessible at the specified domain for successful model interactions.

### 4.2 Performance & Limitations

- **Model Availability:** Only models available on the Ollama server can be utilized. The component checks for model availability during initialization.

## 5. Related Files

### 5.1 Code Files

- [`ollama.py`](../packages/railtracks/src/railtracks/llm/models/local/ollama.py): Contains the implementation of the `OllamaLLM` class for interacting with local Ollama models.

### 5.2 Related Component Files

- [`api_provider_wrappers.md`](../components/api_provider_wrappers.md): Documents the API provider wrappers related to this component.

### 5.3 Related Feature Files

- [`llm_integration.md`](../features/llm_integration.md): Details the integration of language models within the broader system architecture.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
