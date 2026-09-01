# Custom Middleware

The middleware system is designed to support the custom creation of middleware to fit your needs. Each decorator below wraps a plain function into a `Middleware` object. Node-level decorators can be passed to `middleware=` on either `rt.agent_node` or `rt.function_node`. Model-level decorators can only be passed to `model_middleware=` on `rt.agent_node`. A `function_node` never calls a model, so it has no `model_middleware=` slot (the parameter doesn't exist on `function_node`, so passing one is a type/argument error, not a silent no-op).

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



