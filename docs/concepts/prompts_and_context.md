# Prompts and Context Injection

Prompts are a fundamental part of working with LLMs in the Railtracks framework. This guide explains how to create dynamic prompts that use our context injection feature to make your prompts more flexible and powerful.

## Understanding Prompts in Railtracks

In Railtracks, prompts are provided as system messages or user messages when interacting with LLMs. These messages guide the LLM's behavior and responses.


## Context Injection

Railtracks provides a powerful feature called "context injection" (also referred to as "prompt injection") that allows you to dynamically insert values from the global context into your prompts. This makes your prompts more flexible and reusable across different scenarios.

### What is Context Injection?

Context injection refers to the practice of dynamically inserting values into a prompt template. This is especially useful when your prompt needs information that isn't known until runtime.

Passing prompt details up the chain can be expensive in both **tokens** and **latency**. In many cases, it's more efficient to **inject values directly** into a prompt using our [context system](../documentation/advanced/context.md).

### How Context Injection Works

1. Define placeholders in your prompts using curly braces: `{variable_name}`
2. Set values in the Railtracks context (see [Context Management](../documentation/advanced/context.md) for details)
3. When the prompt is processed, the placeholders are replaced with the corresponding values from the context

## Related Topics

* [Tutorials/Prompts and Context](../tutorials/prompts_and_context.md)