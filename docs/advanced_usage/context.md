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

## Quick Start

Here’s how you can use context during a run:

```python
--8<-- "docs/scripts/context.py:context_basics"
```

!!! tip "Context in a Node"
    The context can be accessed from within **any node** in your RailTracks workflow, regardless of where the node is defined or how it's called:
    
    ```python
    --8<-- "docs/scripts/context.py:context_in_node"
    ```

!!! warning
    The context only exists while the run is active. After that, it's gone.

## Real-World Examples

### Prevent Hallucinations in Agentic Systems
In agentic systems, you can use context to store important facts or constraints that agents will need to use. This helps reduce hallucinations by providing a reliable source of truth.

!!! example
    ```python
    --8<-- "docs/scripts/context.py:example"
    ```


### Prompt Injection

One of the most powerful features built on top of the context system is "prompt injection" (also called "context injection"). This allows dynamically inserting values from the global context into prompts for LLMs:

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

