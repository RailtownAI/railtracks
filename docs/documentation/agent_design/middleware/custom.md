# Custom Middleware

The middleware system is designed to support the custom creation of middleware to fit your needs. Each decorator below wraps a plain function into a `Middleware` object that can be passed to `middleware=` (node-level) or `model_middleware=` (model-level) on `rt.agent_node` / `rt.function_node`.

| Decorator | Scope | Runs
|---|---|---|
| `rt.wrap_node` | Node | Wraps the whole node call. You decide if/how many times the inner call runs |
| `rt.after_node` | Node | Once, after the node completes successfully (skipped if it raises) | 
| `rt.wrap_llm` | Model | Wraps the whole model call. You decide if/how many times the inner call runs ||
| `rt.before_llm` | Model | Once, before each model call, to transform the inputs |
| `rt.after_llm` | Model | Once, after each successful model call |

`wrap_node` and `wrap_llm` are the general-purpose forms. Every other decorator is a thin convenience built on top of one of them (`after_node` and `after_llm` only get to run the inner call once and act on its result; `before_llm` only gets to transform the inputs before the inner call runs). 


## Node middleware

```python
--8<-- "docs/scripts/middleware.py:wrappers"
```

```python
--8<-- "docs/scripts/middleware.py:after_node_demo"
```

## Model middleware

```python
--8<-- "docs/scripts/middleware.py:model_middleware_demo"
```



