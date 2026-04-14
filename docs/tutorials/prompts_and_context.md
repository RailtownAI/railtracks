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