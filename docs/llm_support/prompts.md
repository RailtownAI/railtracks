# ✏️ Prompts and Context Injection

Prompts are a fundamental part of working with LLMs in the RailTracks framework. This guide explains how to create dynamic prompts that use our context injection feature to make your prompts more flexible and powerful.

## 🧠 Understanding Prompts in RailTracks

In RailTracks, prompts are provided as system messages or user messages when interacting with LLMs. These messages guide the LLM's behavior and responses. For example:

```python
import railtracks as rt
from railtracks.llm import OpenAILLM

encoder_agent = rt.agent_node(
    name="Encoder",
    system_message="You are an encoder that converts text to base64 encoding.",
    llm_model=OpenAILLM("gpt-4o"),
)
```

## 💉 Context Injection

RailTracks provides a powerful feature called "context injection" (also referred to as "prompt injection") that allows you to dynamically insert values from the global context into your prompts. This makes your prompts more flexible and reusable across different scenarios.

### ❓ What is Context Injection?

Context injection refers to the practice of dynamically inserting values into a prompt template. This is especially useful when your prompt needs information that isn't known until runtime.

Passing prompt details up the chain can be expensive in both **tokens** and **latency**. In many cases, it's more efficient to **inject values directly** into a prompt using our [context system](../advanced_usage/context.md).

### 🔄 How Context Injection Works

1. Define placeholders in your prompts using curly braces: `{variable_name}`
2. Set values in the RailTracks context (see [Context Management](context_management.md) for details)
3. When the prompt is processed, the placeholders are replaced with the corresponding values from the context

### 🚀 Basic Example

```python
import railtracks as rt
from railtracks.llm import OpenAILLM

# Define a prompt with placeholders
system_message = "You are a {role} assistant specialized in {domain}."

# Create an LLM node with this prompt
assistant = rt.agent_node(
    name="Assistant",
    system_message=system_message,
    llm_model=OpenAILLM("gpt-4o"),
)

# Run with context values
with rt.Session(context={"role": "technical", "domain": "Python programming"}):
    response = await rt.call(assistant, user_input="Help me understand decorators.")
```

In this example, the system message will be expanded to: "You are a technical assistant specialized in Python programming."

### 🎛️ Enabling and Disabling Context Injection

Context injection is enabled by default but can be disabled if needed:

```python
import railtracks as rt
from railtracks.llm import MessageHistory, UserMessage

# Create a node with a prompt containing placeholders
my_node = rt.agent_node(
    name="Example",
    system_message="You are a {variable} assistant.",
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
)

# Disable context injection for a specific run
with rt.Session(
        context={"variable": "value"},
        prompt_injection=False
):
    # Context injection will not occur in this run
    user_message = MessageHistory([UserMessage("Hello")])
    response = await rt.call(my_node, user_input=user_message)
```

This may be useful when formatting prompts that should not change based on the context.

### 🔒 Escaping Placeholders

If you need to include literal curly braces in your prompt without triggering context injection, you can escape them by doubling the braces:

```python
# This will not be replaced with a context value
system_message = "Use the {{variable}} placeholder in your code."
```

### 🔍 Debugging Prompts

If your prompts aren't producing the expected results:

1. **Check context values**: Ensure the context contains the expected values for your placeholders
2. **Verify prompt injection is enabled**: Check that `prompt_injection=True` in your session configuration
3. **Look for syntax errors**: Ensure your placeholders use the correct format `{variable_name}`

## 🧩 Advanced Usage

### 📝 Message-Level Control

Context injection can be controlled at the message level using the `inject_prompt` parameter:

```python
from railtracks.llm import Message

# This message will have context injection applied
system_msg = Message(role="system", content="You are a {role}.", inject_prompt=True)

# This message will not have context injection applied
user_msg = Message(role="user", content="Tell me about {topic}.", inject_prompt=False)
```

This can be useful when you want to control which messages should have context injected and which should not. 
As an example, in a Math Assistant, you might want to inject context into the system message, but not the user message that may contain LaTeX that has `{}` characters. To prevent formatting issues, you can set `inject_prompt=False` for the user message.

### 🔄 Dynamic Prompt Templates

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
assistant = rt.agent_node(
    name="Dynamic Assistant",
    system_message=template,
    llm_model=OpenAILLM("gpt-4o"),
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
with rt.Session(context=customer_support_context):
    response1 = await rt.call(assistant, user_input="My product isn't working.")

with rt.Session(context=technical_expert_context):
    response2 = await rt.call(assistant, user_input="How do I implement a binary tree?")
```

## 💡 Benefits of Context Injection

Using context injection provides several advantages:

1. **Reduced token usage**: Avoid passing the same context information repeatedly
2. **Improved maintainability**: Update prompts in one place
3. **Dynamic adaptation**: Adjust prompts based on runtime conditions
4. **Separation of concerns**: Keep prompt templates separate from variable data
5. **Reusability**: Use the same prompt template with different contexts