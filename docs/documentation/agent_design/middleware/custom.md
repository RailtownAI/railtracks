# Custom Middleware

The middleware system is designed to support the custom creation of middleware to fit your needs. Each decorator below wraps a plain function into a `Middleware` object. Node-level decorators can be passed to `middleware=` on either an [agent node](../overview.md#agent-node) or a [function node](../tools/function_tools.md#what-a-function-node-is). Model-level decorators can only be passed to `model_middleware=` on `rt.agent_node`. A `function_node` never calls a model, so it has no `model_middleware=` slot (the parameter doesn't exist on `function_node`, so passing one is a type/argument error, not a silent no-op).

| Decorator | Scope | Runs
|---|---|---|
| `rt.wrap_node` | Node | Wraps the whole node call. You decide if/how many times the inner call runs |
| `rt.post_node` | Node | Once, after the node completes successfully (skipped if it raises) | 
| `rt.wrap_llm` | Model | Wraps the whole model call. You decide if/how many times the inner call runs ||
| `rt.pre_llm` | Model | Once, before each model call, to transform the inputs |
| `rt.post_llm` | Model | Once, after each successful model call |

`wrap_node` and `wrap_llm` are the general-purpose forms. Every other decorator is a thin convenience built on top of one of them (`post_node` and `post_llm` only get to run the inner call once and act on its result; `pre_llm` only gets to transform the inputs before the inner call runs). 

!!! note "`wrap_node` / `wrap_llm` functions must be `async def`"
    `wrap_node` and `wrap_llm` re-invoke the inner call directly, so the function you decorate must be defined with `async def`. A plain `def` raises `TypeError` immediately for `wrap_node`, or fails with a confusing "can't be used in 'await' expression" error at call time for `wrap_llm`. `post_node`, `pre_llm`, and `post_llm` are more forgiving: they accept either a plain `def` or an `async def`.

## Node middleware

```python
--8<-- "docs/scripts/middleware.py:wrappers"
```

```python
--8<-- "docs/scripts/middleware.py:post_node_demo"
```

The same middleware attaches to a `function_node` exactly the same way, via `middleware=`:

```python
--8<-- "docs/scripts/middleware.py:function_node_demo"
```

## Model middleware

```python
--8<-- "docs/scripts/middleware.py:model_middleware_demo"
```

## Middleware state

A middleware object is shared, never copied. Every node you attach it to (in either slot), every node `rt.couple` builds from those, and every run of every Flow, including runs happening at the same time, call the same instance. A plain attribute is therefore shared by all of them, which is what you want for configuration and resources. For state that belongs to one run, such as a counter or a budget, declare a `RunLocal` field: you read and write it like any attribute, but every run gets its own value.

| Declared as | Each run sees | Use it for |
|---|---|---|
| A plain attribute (`self.client = ...`) | The same value as every other run, concurrent ones included | Configuration and resources: a client, a connection pool, a semaphore |
| A `RunLocal` field (`calls = RunLocal(int)`) | Its own value, starting from the default | Per-run counters, budgets, and scratch state |

```python
--8<-- "docs/scripts/middleware.py:per_run_state"
```

`RunLocal` takes a factory rather than a value (`RunLocal(int)`, `RunLocal(list)`, `RunLocal(lambda: {"tokens": 0})`), so a mutable default is fresh in every run. Within one run, every node the instance is attached to shares the value, so one `CountCalls` on two tools counts both. Outside a run, the field holds the most recent run's value, so `counter.calls` tells you what a run did once `invoke()` returns, and `del counter.calls` resets it. The value lives with the run and ends with it: it is not part of `rt.context` and is never saved.

`RunLocal` fields are declared on a class, so decorator-built middleware (`@rt.wrap_node` and the others) has nowhere to put one. When a decorator middleware needs per-run state, write it as a `Middleware` subclass as above.

The prebuilt middleware are good references: [`MaxCalls`](prebuilt/list/max_calls.md) keeps its count in a `RunLocal`, [`ConversationMemory`](prebuilt/list/conversation_memory.md) deliberately keeps its history across runs so a conversation can carry on over several `invoke()` calls, and [`Lock`](prebuilt/list/lock.md) serializes the calls that share it.

!!! warning "Plain attributes are shared across concurrent runs"
    A per-run value kept in a plain attribute mixes runs together: two runs in flight at once both read and write it, and a run sees whatever the previous one left behind. Declare it as a `RunLocal` instead. When runs genuinely need to coordinate on shared state, put a [`Lock`](prebuilt/list/lock.md) outside the middleware that uses it.



