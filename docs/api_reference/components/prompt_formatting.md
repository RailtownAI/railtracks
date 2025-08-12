# Prompt Injection

The Prompt Injection component provides functionality to format and inject values into message prompts using a custom formatter and dictionary. This is particularly useful in scenarios where dynamic data needs to be inserted into predefined prompt templates, enhancing the flexibility and adaptability of the system.

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

The primary purpose of the Prompt Injection component is to enable the dynamic insertion of values into message prompts. This is achieved through a custom formatter and a dictionary that holds the values to be injected. The component is essential for adapting prompts to the current execution context, especially when certain data is only available at runtime.

### 1.1 Dynamic Prompt Filling

This use case involves filling a prompt with dynamic values using the `fill_prompt` function. This is crucial for scenarios where the prompt template contains placeholders that need to be replaced with actual data at runtime.

python
from railtracks.utils.prompt_injection import fill_prompt, ValueDict

prompt_template = "Find the capital of {country}."
values = ValueDict(country="France")
filled_prompt = fill_prompt(prompt_template, values)
print(filled_prompt)  # Output: "Find the capital of France."


### 1.2 Message History Injection

This use case demonstrates how to inject values into a series of messages using the `inject_values` function. This is important for maintaining a consistent and contextually relevant message history.

python
from railtracks.llm import MessageHistory, Message
from railtracks.utils.prompt_injection import inject_values, ValueDict

message_history = MessageHistory([
    Message(content="Find the capital of {country}.", role="user", inject_prompt=True)
])
values = ValueDict(country="Germany")
updated_history = inject_values(message_history, values)
print(updated_history)  # Output: "user: Find the capital of Germany."


## 2. Public API

### `class KeyOnlyFormatter(string.Formatter)`
A simple formatter which will only use keyword arguments to fill placeholders.

#### `.get_value(self, key, args, kwargs)`
No docstring found.


---
### `class ValueDict(dict)`
No docstring found.


---
### `def fill_prompt(prompt, value_dict)`
Fills a prompt using the railtracks context object as its source of truth


---
### `def inject_values(message_history, value_dict)`
Injects the values in the `value_dict` from the current request into the prompt.

Args:
    message_history (MessageHistory): The prompts to inject context into.
    value_dict (ValueDict): The dictionary containing values to fill in the prompt.


---

## 3. Architectural Design

The Prompt Injection component is designed to provide a flexible and efficient way to inject dynamic values into message prompts. The design leverages Python's `string.Formatter` to create a custom formatter (`KeyOnlyFormatter`) that only uses keyword arguments for filling placeholders. This ensures that only specified keys are replaced, preventing accidental overwrites.

### 3.1 KeyOnlyFormatter

- **Purpose:** Custom formatter that uses only keyword arguments.
- **Design Consideration:** Ensures that only specified keys are replaced, maintaining the integrity of the prompt template.

### 3.2 ValueDict

- **Purpose:** Custom dictionary that returns placeholders for missing keys.
- **Design Consideration:** Provides a fallback mechanism for missing values, ensuring that the prompt structure is preserved even if some data is unavailable.

## 4. Important Considerations

### 4.1 Dependencies & Setup

- The component relies on the `railtracks.llm` module for message handling. Ensure that this module is correctly configured and available in the environment.

### 4.2 Performance & Limitations

- The component is designed for efficiency, but injecting a large number of values or handling extensive message histories may impact performance. Consider optimizing the value dictionary and message history size for better performance.

## 5. Related Files

### 5.1 Code Files

- [`prompt_injection.py`](../packages/railtracks/src/railtracks/utils/prompt_injection.py): Contains the implementation of the Prompt Injection component.

### 5.2 Related Component Files

- [`message.py`](../packages/railtracks/src/railtracks/llm/message.py): Defines the `Message` class used in message handling.
- [`history.py`](../packages/railtracks/src/railtracks/llm/history.py): Defines the `MessageHistory` class used for managing message sequences.

### 5.3 Related Feature Files

- [`llm_integration.md`](../docs/llm_support/prompts.md): Provides additional context on how prompt injection is used within the larger LLM integration framework.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
