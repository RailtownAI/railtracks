# ✏️ Prompt Injection

Passing prompt details up the chain can be expensive in both **tokens** and **latency**. In many cases, it’s more efficient to **inject values directly** into a prompt using our [context system](../context).

## ❓ What is Prompt Injection?

Prompt injection refers to the practice of **dynamically inserting values** into a prompt template. This is especially useful when your prompt is waiting for input that isn't known ahead of time.

For example:

```python
"Find the capital of {country}."
```

Here, the `{country}` placeholder will be replaced with a specific country name at runtime.

!!! tip
    Prompt injection is helpful when you want to **adapt your prompt** to the current execution context or when you only have certain data available at runtime.

---

📚 For more on how to use prompt injection effectively, check out the [Prompts documentation](../../llm_support/prompts).
