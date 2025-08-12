# Prompt Injection

The Prompt Injection component is designed to inject context from the current request into a message history for prompt processing within the Railtracks framework. This allows for dynamic and context-aware interactions with language models.

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

The primary purpose of the Prompt Injection component is to enhance the interaction with language models by injecting relevant context into the message history. This is particularly useful in scenarios where the context of a session or request needs to be considered to generate accurate and relevant responses.

### 1.1 Injecting Context into Message History

This use case involves injecting the current request's context into a `MessageHistory` object, which is then used to interact with language models.

python
from railtracks.llm import MessageHistory
from railtracks.prompts.prompt import inject_context

# Create a MessageHistory object
message_history = MessageHistory()

# Inject context into the message history
inject_context(message_history)

# Use the message history with a language model
response = language_model.process(message_history)


## 2. Public API

### `def inject_context(message_history)`
Injects the context from the current request into the prompt.

Args:
    message_history (MessageHistory): The prompts to inject context into.


---

## 3. Architectural Design

### 3.1 Context Injection Mechanism

- **_ContextDict Class:**
  - Inherits from `ValueDict` and overrides the `__getitem__` method to fetch context values using `context.get(key)`.
  - This design allows seamless integration of context values into the message history.

- **inject_context Function:**
  - Attempts to retrieve the local configuration using `get_local_config()`.
  - Checks if prompt injection is enabled via `local_config.prompt_injection`.
  - If enabled, it uses `inject_values` to inject context into the `MessageHistory` using `_ContextDict`.

- **Design Considerations:**
  - The component is designed to handle cases where the context is not set, such as when not running within an `rt.Session()`.
  - The use of exceptions (`ContextError`) ensures robust handling of missing context scenarios.

## 4. Important Considerations

### 4.1 Context Management

- The component relies on the `railtracks.context` module to fetch and manage context values.
- It is crucial to ensure that the context is correctly set up and managed to avoid `ContextError`.

### 4.2 Performance and Limitations

- The performance of context injection is dependent on the efficiency of the `context.get` method and the size of the context being injected.
- The component is not suitable for scenarios where context management is not properly configured.

## 5. Related Files

### 5.1 Code Files

- [`../packages/railtracks/src/railtracks/prompts/prompt.py`](../packages/railtracks/src/railtracks/prompts/prompt.py): Contains the implementation of the Prompt Injection component.

### 5.2 Related Component Files

- [`../components/context_management.md`](../components/context_management.md): Provides documentation on context management within the Railtracks framework.

### 5.3 Related Feature Files

- [`../features/llm_integration.md`](../features/llm_integration.md): Details the integration of language models with the Railtracks framework.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
