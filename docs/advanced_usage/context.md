# Global Context

RailTracks includes a concept of global context, letting you store and retrieve shared information across the lifecycle of a run. This makes it easy to coordinate data like config settings, environment flags, or shared resources.

## What is Global Context?

The context system gives you a simple and clear API for interacting with shared values. It's scoped to the duration of a run, so everything is neatly contained within that execution lifecycle. One of the key features of the context system is that it can be accessed from within any node in your workflow, making it ideal for sharing data between different parts of your application.

## Core Functions

You can use the context with the following main functions:

* `rt.context.get(key, default=None)` - Retrieves a value from the context
* `rt.context.put(key, value)` - Stores a value in the context
* `rt.context.update(dict)` - Updates multiple values in the context at once
* `rt.context.delete(key)` - Removes a value from the context

## Quick Example

Here’s how you can use context during a run:

```python
import railtracks as rt

# Set up some context data
data = {"var_1": "value_1"}

with rt.Session(context=data):
    rt.context.get("var_1")  # Outputs: value_1
    rt.context.get("var_2", "default_value")  # Outputs: default_value

    rt.context.put("var_2", "value_2")  # Sets var_2 to value_2
    rt.context.put("var_1", "new_value_1")  # Replaces var_1 with new_value_1
```

!!! tip "Context in Any Node"
    The context can be accessed from within **any node** in your RailTracks workflow, regardless of where the node is defined or how it's called:
    
    ```python
    import railtracks as rt
    
    @rt.to_node
    def some_node():
        return rt.context.get("var_1")
    
    with rt.Runner(context={"var_1": "value_1"}):
        await rt.call(some_node)
    ```

!!! warning
    The context only exists while the run is active. After that, it's gone.

## Real-World Examples

### Prevent Hallucinations in Agentic Systems
In agentic systems, you can use context to store important facts or constraints that agents will need to use. This helps reduce hallucinations by providing a reliable source of truth.

```python
import railtracks as rt
from railtracks import agent_node, context
from railtracks.llm import OpenAILLM

# Define a tool that uses context
@rt.function_node
def find_issue(input: str) -> str:
    issue = get_issue_from_input(input)  # Assume this function finds an issue number from the input
    return context.put("issue_number", issue)

@rt.function_node
def comment_on_issue(comment: str):
    try:
        issue = context.get("issue_number")
    except KeyError:
        return "No relevant issue is available."
    
    comment_on_github_issue(issue, comment)  # Assume this function comments on the issue

# Define the agent with the tool
GitHubAgent = agent_node(
    tool_nodes=[find_issue, comment_on_issue],
    llm=OpenAILLM("gpt-4o"),
    system_message="You are an agent that provides information based on important facts.",
)

# Run the agent
with rt.Session:
    response = await rt.call(
        GitHubAgent,
        "What is the last issue created? Please write a comment on it."
    )
```


### Prompt Injection

One of the most powerful features built on top of the context system is "prompt injection" (also called "context injection"). This allows dynamically inserting values from the global context into prompts for LLMs:

```python
import railtracks as rt
from railtracks.llm import OpenAILLM

# Define a prompt with placeholders
system_message = "You are a {assistant_type} assistant. The user's name is {user_name}."

# Create an LLM node with this prompt
assistant = rt.agent_node(
    name="Assistant",
    system_message=system_message,
    llm=OpenAILLM("gpt-4o"),
)

# Run with context values
with rt.Session(context={
    "assistant_type": "friendly and helpful",
    "user_name": "Alex"
}):
    response = await rt.call(
        assistant, 
        user_input="Can you help me with my project?"
    )
```

In this example, the system message will be expanded to: "You are a friendly and helpful assistant. The user's name is Alex."

!!! tip
    For more details on prompt injection, see the [Prompts and Context Injection](../llm_support/prompts.md) documentation.

## Benefits of Using Context

!!! info "Why use the context system?"
    The context system provides several advantages over alternatives like global variables

1. **Safer and clearer** way to manage shared values
2. Makes runs more **predictable**
3. Makes data easier to **reason about**
4. **Reduces repetitive code**
5. Keeps **sensitive information** out of LLM inputs
6. Provides **clean scoping** tied to execution lifecycle

