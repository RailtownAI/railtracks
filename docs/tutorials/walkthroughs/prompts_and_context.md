### Enabling Context Injection

Context injection is **opt-in per agent**: add `rt.middleware.ContextInjection()` to an agent's `model_middleware` to turn on placeholder substitution. Agents without this middleware leave `{placeholders}` untouched.

```python
--8<-- "docs/scripts/prompts.py:prompt_basic"
```

Because the agent includes `ContextInjection`, its system message is expanded at call time to: "You are a technical assistant specialized in Python programming." Drop the middleware and the model would receive the literal `{role}` / `{domain}` text instead.

### Disabling Context Injection

Once an agent opts in, injection can still be suppressed at several levels, from broadest to narrowest scope:

| Scope | How | Applies to |
| --- | --- | --- |
| **Global** | `rt.set_config(prompt_injection=False)` | Every flow/run, unless a flow overrides it |
| **Flow** | `prompt_injection=False` on `rt.Flow(...)` | Every run of that flow |
| **Agent / node** | omit `rt.middleware.ContextInjection()` from `model_middleware` on `rt.agent_node(...)` | Every instantiation of that node |
| **Message** | `inject_prompt=False` on a `SystemMessage` / `UserMessage` | That single message |

#### Precedence

The agent-level middleware is the master switch: with no `ContextInjection` entry, nothing is injected regardless of the other settings. When it *is* present, the remaining levels act as independent gates — a placeholder is filled **only when injection is enabled at every applicable level**. The most restrictive setting wins, and a narrower scope cannot re-enable injection that a broader scope has turned off.

The one exception is the run-wide flag itself: a **Flow's `prompt_injection` overrides the global `rt.set_config` value**. If the flow does not set it, the global value applies; if neither is set, the default (`True`) is used.

#### Agent / node level

Only agents whose `model_middleware` contains `rt.middleware.ContextInjection()` substitute placeholders. An agent whose prompt legitimately contains `{}` braces that should be left untouched simply omits the middleware:

```python
--8<-- "docs/scripts/prompts.py:disable_injection_node_level"
```

#### Global and Flow level

For an agent that *does* use `ContextInjection`, you can still switch injection off for a whole run or globally:

```python
--8<-- "docs/scripts/prompts.py:disable_injection"
```

This may be useful when formatting prompts that should not change based on the context.

!!! note "Message-Level Control"

    Context injection can also be controlled at the message level using the `inject_prompt` parameter:

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
2. **Verify prompt injection is enabled**: Check that `prompt_injection` is not disabled globally (`rt.set_config`) or on the flow, that the agent's `model_middleware` includes `rt.middleware.ContextInjection()`, and that the message was not created with `inject_prompt=False`
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