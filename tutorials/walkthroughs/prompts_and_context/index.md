### Enabling Context Injection

Context injection is **opt-in per agent**: add `rt.prebuilt.middleware.ContextInjection()` to an agent's `model_middleware` to turn on placeholder substitution. Agents without this middleware leave `{placeholders}` untouched. See [Context Injection](https://docs.railtracks.org/documentation/agent_design/middleware/prebuilt/list/context_injection/index.md) for the middleware's own reference, including how list position affects what other middleware sees.

```python
import railtracks as rt

# Define a prompt with placeholders
system_message = "You are a {role} assistant specialized in {domain}."

# Create an LLM node with this prompt. ContextInjection() enables placeholder
# substitution from rt.context; without it the {placeholders} are left as-is.
Assistant = rt.agent_node(
    name="Assistant",
    system_message=system_message,
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    model_middleware=[rt.prebuilt.middleware.ContextInjection()],
)

# Run with context values
assistant_flow = rt.Flow("assistant-flow", entry_point=Assistant)
response = assistant_flow.update_context({"role": "technical", "domain": "Python programming"}).invoke("Help me understand decorators.")
```

Because the agent includes `ContextInjection`, its system message is expanded at call time to: "You are a technical assistant specialized in Python programming." Drop the middleware and the model would receive the literal `{role}` / `{domain}` text instead.

### Disabling Context Injection

The middleware is the only switch. Only agents whose `model_middleware` contains `rt.prebuilt.middleware.ContextInjection()` substitute placeholders, so an agent whose prompt legitimately contains `{}` braces that should be left untouched simply omits it:

```python
# Injection is opt-in: an agent that omits rt.prebuilt.middleware.ContextInjection()
# from its model_middleware leaves {placeholders} untouched.
LiteralAssistant = rt.agent_node(
    name="Literal Assistant",
    system_message="Always answer using the {placeholder} syntax verbatim.",
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
)
```

### Escaping Placeholders

If you need to include literal curly braces in your prompt without triggering context injection, you can escape them by doubling the braces:

```python
# This will not be replaced with a context value
"Use the {{variable}} placeholder in your code."
```

For a string you did not write yourself, such as user input or a fetched document, use `rt.escape_braces` to double its braces for you. This lets one message hold both a template you wrote and text that is delivered as written:

```python
prompt = f"The current time is {{time}}:\nUser Message:\n{rt.escape_braces(user_text)}"
```

### Debugging Prompts

If your prompts aren't producing the expected results:

1. **Check context values**: Ensure the context contains the expected values for your placeholders
1. **Verify context injection is enabled**: It is not on by default — check that the agent's `model_middleware` includes `rt.prebuilt.middleware.ContextInjection()` ([how to add it](https://docs.railtracks.org/documentation/agent_design/middleware/prebuilt/list/context_injection/index.md))
1. **Look for syntax errors**: Ensure your placeholders use the correct format `{variable_name}`

## Example (Reusable Prompt Templates)

You can create reusable prompt templates that adapt to different scenarios:

```python
import railtracks as rt
from railtracks.llm import OpenAILLM

# Define a template with multiple placeholders
template = """You are a {assistant_type} assistant.
Your task is to help the user with {task_type} tasks.
Use a {tone} tone in your responses.
The user's name is {user_name}."""

# Create an LLM node with this template
DynamicAssistant = rt.agent_node(
    name="Dynamic Assistant",
    system_message=template,
    llm=OpenAILLM("gpt-6-luna"),
    model_middleware=[rt.prebuilt.middleware.ContextInjection()],
)

# Different context for different scenarios
customer_support_context = {
    "assistant_type": "customer support",
    "task_type": "troubleshooting",
    "tone": "friendly and helpful",
    "user_name": "Alex"
}

technical_expert_context = {
    "assistant_type": "technical expert",
    "task_type": "programming",
    "tone": "professional",
    "user_name": "Taylor"
}

# Run with different contexts for different scenarios
assistant_flow = rt.Flow("assistant-flow", entry_point=DynamicAssistant)
customer_support_flow = assistant_flow.update_context(customer_support_context)
response1 = customer_support_flow.invoke("My internet is not working. Can you help?")

technical_expert_flow = assistant_flow.update_context(technical_expert_context)
response2 = technical_expert_flow.invoke("How do I implement a binary tree?")
```

## Benefits of Context Injection

Using context injection provides several advantages:

1. **Reduced token usage**: Avoid passing the same context information repeatedly
1. **Improved maintainability**: Update prompts in one place
1. **Dynamic adaptation**: Adjust prompts based on runtime conditions
1. **Separation of concerns**: Keep prompt templates separate from variable data
1. **Reusability**: Use the same prompt template with different contexts
