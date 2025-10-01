# Prompts and Context Injection

Prompts are a fundamental part of working with LLMs in the Railtracks framework. This guide explains how to create dynamic prompts that use our context injection feature to make your prompts more flexible and powerful.

## Understanding Prompts in Railtracks

In Railtracks, prompts are provided as system messages or user messages when interacting with LLMs. These messages guide the LLM's behavior and responses.


## Context Injection

Railtracks provides a powerful feature called "context injection" (also referred to as "prompt injection") that allows you to dynamically insert values from the global context into your prompts. This makes your prompts more flexible and reusable across different scenarios.

### What is Context Injection?

Context injection refers to the practice of dynamically inserting values into a prompt template. This is especially useful when your prompt needs information that isn't known until runtime.

Passing prompt details up the chain can be expensive in both **tokens** and **latency**. In many cases, it's more efficient to **inject values directly** into a prompt using our [context system](../advanced_usage/context.md).

### How Context Injection Works

1. Define placeholders in your prompts using curly braces: `{variable_name}`
2. Set values in the Railtracks context (see [Context Management](../advanced_usage/context.md) for details)
3. When the prompt is processed, the placeholders are replaced with the corresponding values from the context

### Basic Example

```python
--8<-- "docs/scripts/prompts.py:prompt_basic"
```

In this example, the system message will be expanded to: "You are a technical assistant specialized in Python programming."

### Enabling and Disabling Context Injection

Context injection is enabled by default but can be disabled if needed:

```python
--8<-- "docs/scripts/prompts.py:disable_injection"
```

This may be useful when formatting prompts that should not change based on the context.

!!! note "Message-Level Control"

    Context injection can be controlled at the message level using the `inject_prompt` parameter:

    ```python
    --8<-- "docs/scripts/prompts.py:injection_at_message_level"
    ```

    This can be useful when you want to control which messages should have context injected and which should not. 

    As an example, in a Math Assistant, you might want to inject context into the system message, but not the user message that may contain LaTeX that has `{}` characters. To prevent formatting issues, you can set `inject_prompt=False` for the user message.

### Escaping Placeholders

If you need to include literal curly braces in your prompt without triggering context injection, you can escape them by doubling the braces:

```python
# This will not be replaced with a context value
"Use the {{variable}} placeholder in your code."
```

### Debugging Prompts

If your prompts aren't producing the expected results:

1. **Check context values**: Ensure the context contains the expected values for your placeholders
2. **Verify prompt injection is enabled**: Check that `prompt_injection=True` in your session configuration
3. **Look for syntax errors**: Ensure your placeholders use the correct format `{variable_name}`




## Example (Reusable Prompt Templates)

You can create reusable prompt templates that adapt to different scenarios:

```python
--8<-- "docs/scripts/prompts.py:prompt_templates"
```

## Benefits of Context Injection

Using context injection provides several advantages:

1. **Reduced token usage**: Avoid passing the same context information repeatedly
2. **Improved maintainability**: Update prompts in one place
3. **Dynamic adaptation**: Adjust prompts based on runtime conditions
4. **Separation of concerns**: Keep prompt templates separate from variable data
5. **Reusability**: Use the same prompt template with different contexts