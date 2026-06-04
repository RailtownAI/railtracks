### Basic Example

```python
--8<-- "docs/scripts/prompts.py:prompt_basic"
```

In this example, the system message will be expanded to: "You are a technical assistant specialized in Python programming."

### Enabling and Disabling Context Injection

Context injection is enabled by default. It can be disabled at three levels — from broadest to narrowest:

```python
--8<-- "docs/scripts/prompts.py:disable_injection"
```

**Choosing the right level:**

| Level | API | When to use |
|---|---|---|
| **LLM level** | `agent_node(context_injection=False)` | A specific agent should never do injection, regardless of session config |
| **Session level** | `rt.Session(prompt_injection=False)` or `rt.Flow(..., prompt_injection=False)` | Disable injection for one session or run |
| **Global level** | `rt.set_config(prompt_injection=False)` | Disable injection everywhere for the current process |

The LLM-level flag short-circuits the session setting — if `context_injection=False` on the node class, the session config is irrelevant for that node.

!!! note "Message-Level Control"

    Context injection can also be controlled at the message level using the `inject_prompt` parameter:

    ```python
    --8<-- "docs/scripts/prompts.py:injection_at_message_level"
    ```

    This is the most granular option. For example, in a Math Assistant you might inject context into the system message but not the user message, which may contain LaTeX `{}` characters that would otherwise be treated as placeholders.

### Escaping Placeholders

If you need to include literal curly braces in your prompt without triggering context injection, you can escape them by doubling the braces:

```python
# This will not be replaced with a context value
"Use the {{variable}} placeholder in your code."
```

### Debugging Prompts

If your prompts aren't producing the expected results:

1. **Check context values**: Ensure the context contains the expected values for your placeholders
2. **Verify prompt injection is not disabled**: Context injection is on by default — check that `prompt_injection=False` has not been set in your session, flow, or global config
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