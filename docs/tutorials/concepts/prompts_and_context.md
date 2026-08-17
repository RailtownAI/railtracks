# Prompts and Context Injection

Prompts are a fundamental part of working with LLMs in the Railtracks framework. This guide explains how to create dynamic prompts that use our context injection feature to make your prompts more flexible and powerful.

## Understanding Prompts in Railtracks

In Railtracks, prompts are provided as system messages or user messages when interacting with LLMs. These messages guide the LLM's behavior and responses.


## Context Injection

Railtracks provides a powerful feature called "context injection" (also referred to as "prompt injection") that allows you to dynamically insert values from the global context into your prompts. This makes your prompts more flexible and reusable across different scenarios.

### What is Context Injection?

Context injection refers to the practice of dynamically inserting values into a prompt template. This is especially useful when your prompt needs information that isn't known until runtime.

Passing prompt details up the chain can be expensive in both **tokens** and **latency**. In many cases, it's more efficient to **inject values directly** into a prompt using our [context system](../../documentation/advanced/context.md).

### How Context Injection Works

1. Define placeholders in your prompts using curly braces: `{variable_name}`
2. Set values in the Railtracks context (see [Context Management](../../documentation/advanced/context.md) for details)
3. When the prompt is processed, the placeholders are replaced with the corresponding values from the context

Only a placeholder naming a context key on its own is replaced. A placeholder that reaches into a
value, such as `{config.host}` or `{config[host]}`, is left in the prompt as written, as is a
placeholder whose key is not in the context. Write `{{` and `}}` for a literal brace.

### Untrusted text in a prompt

Placeholders are filled in user messages as well as system messages, so text you did not write
yourself is also a template. Pass such text through `rt.escape_braces` before putting it in a prompt
so its braces are treated as data:

```python
prompt = f"The current time is {{time}}:\nUser Message:\n{rt.escape_braces(user_text)}"
```

`{time}` is filled from the context, while anything inside `user_text` is delivered to the model
exactly as written. Keep secrets out of the context of any agent that handles untrusted text: a
context key named in that text is still filled if it is not escaped.

## Related Topics

* [Tutorials/Prompts and Context](../walkthroughs/prompts_and_context.md)