### Enabling Context Injection

Context injection is **opt-in per agent**: add `rt.middleware.ContextInjection()` to an agent's `model_middleware` to turn on placeholder substitution. Agents without this middleware leave `{placeholders}` untouched.

```python
--8<-- "docs/scripts/prompts.py:prompt_basic"
```

Because the agent includes `ContextInjection`, its system message is expanded at call time to: "You are a technical assistant specialized in Python programming." Drop the middleware and the model would receive the literal `{role}` / `{domain}` text instead.

### Disabling Context Injection

The middleware is the only switch. Only agents whose `model_middleware` contains `rt.middleware.ContextInjection()` substitute placeholders, so an agent whose prompt legitimately contains `{}` braces that should be left untouched simply omits it:

```python
--8<-- "docs/scripts/prompts.py:disable_injection_node_level"
```

### Escaping Placeholders

If you need to include literal curly braces in your prompt without triggering context injection, you can escape them by doubling the braces:

```python
# This will not be replaced with a context value
"Use the {{variable}} placeholder in your code."
```

For a string you did not write yourself, such as user input or a fetched document, use
`rt.escape_braces` to double its braces for you. This lets one message hold both a template you wrote
and text that is delivered as written:

```python
prompt = f"The current time is {{time}}:\nUser Message:\n{rt.escape_braces(user_text)}"
```

### Debugging Prompts

If your prompts aren't producing the expected results:

1. **Check context values**: Ensure the context contains the expected values for your placeholders
2. **Verify prompt injection is enabled**: Check that the agent's `model_middleware` includes `rt.middleware.ContextInjection()`
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