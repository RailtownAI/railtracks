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

A middleware object is shared, never copied. Every node you attach it to (in either slot), every node `rt.couple` builds from those, and every run of every Flow, including runs happening at the same time, call the same instance. Where the middleware keeps its state decides how far that state reaches:

| State kept in | Shared by | Use it for |
|---|---|---|
| The instance (`self.client`) or a closure variable | Every run in the process, including concurrent ones | Configuration and process-wide resources: a client, a connection pool, a semaphore |
| [`rt.context.local`](../../advanced/context.md#state-owned-by-a-middleware-or-node) | One session; each run starts from a fresh value | Anything that changes during a run: counters, budgets, scratch values |

`rt.context.local(cls)` returns this session's instance of `cls` for the middleware that is running, creating it with `cls()` on first use. Railtracks works out the owner from what is running, so there is no key to choose, and the same call works in a decorator-built middleware, a `Middleware` subclass, or a tool. This counter starts from zero in every run, and concurrent runs never see each other's count:

```python
--8<-- "docs/scripts/middleware.py:per_run_state"
```

To read a middleware's state from somewhere else in the run, such as the node that drives it, pass the instance: `rt.context.local(CallCount, owner=count_calls)`. [`MaxCalls`](prebuilt/list/max_calls.md) keeps its budget this way. [`ConversationMemory`](prebuilt/list/conversation_memory.md) stores its history in `rt.context` instead, under a key you can name, so the history can be seeded, shared between nodes, or read from the flow's context. [`Lock`](prebuilt/list/lock.md) serializes the calls that share it.

!!! warning "Instance state is shared across concurrent runs"
    A per-run value kept on `self` mixes runs together: two runs in flight at once both read and write it, and a run sees whatever the previous one left behind. Keep per-run state in `rt.context.local`. When runs genuinely need to coordinate on shared state, put a [`Lock`](prebuilt/list/lock.md) outside the middleware that uses it.



