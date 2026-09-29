# Global Context

Railtracks includes a concept of global context, letting you store and retrieve shared information across the lifecycle of a run. This makes it easy to coordinate data like config settings, environment flags, or shared resources.

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

!!! warning
    The context only exists while the run is active. After that, it's gone.

## Real-World Examples

For a complete example that carries conversation history between nodes through context, see [Message History](../invocation/message_history.md#share-history-between-nodes-in-one-run).

### Prevent Hallucinations in Agentic Systems
In agentic systems, you can use context to store important facts or constraints that agents will need to use. This helps reduce hallucinations by providing a reliable source of truth.

!!! example
    ```python
    --8<-- "docs/scripts/context.py:example"
    ```


### Context Injection

One of the most powerful features built on top of the context system is "context injection". This allows dynamically inserting values from the global context into prompts for LLMs:

!!! tip
    For more details on context injection, see the [Prompts and Context Injection Tutorial](../../tutorials/walkthroughs/prompts_and_context.md) documentation.

## Observability

Each `rt.context` call your code makes is recorded in the run's event stream. Every context event carries `keys`, the list of keys it touched, and `values`, a dict of those keys to their values:

| Event | `keys` and `values` |
| --- | --- |
| `context.creation` | everything the run starts with, plus the `level` it was recorded at |
| `context.get` | the key read, and the value it returned (the default, on a miss) |
| `context.put` | the key and value set |
| `context.update` | the keys and values passed in |
| `context.delete` | the key removed; `values` is `null` |
| `context.completion` | everything the run ends with, plus the `level` |

To find every event that touched a key, filter on `keys` alone: it covers every event type.

Values are recorded as they were at the moment of the call. A call that raises `KeyError` records nothing, and `rt.context.keys()` is never recorded. Values are recorded in full, so a large value is written to the event file on every event that carries it.

!!! warning "Editing a value in place is not recorded"
    `rt.context` hands you the stored object, not a copy, so `rt.context.get("cart").append("pear")` changes the context without a `put`. At level `2`, such an edit only shows up in `context.completion`; at level `1` it doesn't show up at all.

Railtracks' own use of the context isn't recorded, to keep the log to your code's calls. For example, `ConversationMemory`'s history and the reads behind [context injection](#context-injection) don't appear.

### Choosing what's recorded

Set `RAILTRACKS_CONTEXT_EVENTS` to choose how much of each call is recorded:

| Value | What's recorded |
| --- | --- |
| `0` | No context events. |
| `1` | Every context event, with its keys but no values: `values` is `null`. |
| `2` (default) | Every context event, with keys and values. |

Use `1` when your context holds large values or data you'd rather not have in the event files, and `0` to leave context out entirely. Any other value is treated as `2`, with a warning. Other events are recorded either way.

```bash
export RAILTRACKS_CONTEXT_EVENTS=1
```

## Benefits of Using Context

!!! info "Why use the context system?"
    The context system provides several advantages over alternatives like global variables

1. **Safer and clearer** way to manage shared values
2. Makes runs more **predictable**
3. Makes data easier to **reason about**
4. **Reduces repetitive code**
5. Keeps **sensitive information** out of LLM inputs
6. Provides **clean scoping** tied to execution lifecycle
