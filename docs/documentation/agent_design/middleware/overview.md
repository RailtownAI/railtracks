# Middleware

Middleware is a pervasive software concept. One which, when applied to the tooling of an agent, can have immense power and clean composability. At its core, middleware in railtracks is a function which wraps your node's call. Concretely, middleware can do things like:

- Log inputs and outputs
- Handle automatic retries
- PII detection and redaction
- Unwanted Question rejection

The beauty of this concept is how easy it is to compose middleware and add it to your flows. Below you can see a simple example of injecting a retry middleware into a flow.

```python
--8<-- "docs/scripts/middleware.py:wrappers"
```

## Prebuilt Middleware
We provide a suite of prebuilt middleware for common use cases. Check out the complete list of [prebuilt middleware](prebuilt/overview.md). For custom creation of middleware you can use our guide to building your own [custom middleware](custom.md).

## Types of Middleware

### Middleware (Regular)
Most middleware will wrap an entire node or function call. Common examples include logging, retry logic, HIL verification, rate limiting, caching, and more. Outside of what we supply, you can create your own with a small decorator API.

| Decorator | Runs |
|---|---|
| `rt.wrap_node` | Wraps the whole node call — you decide if/how many times the inner call runs 
| `rt.after_node` | Once, after the node completes successfully (skipped if the node raises)

`rt.wrap_node` is the general-purpose form — the retry example above is built on it. `rt.after_node` is a narrower convenience for the common "do something with the result and pass it through" case:

```python
--8<-- "docs/scripts/middleware.py:after_node_demo"
```

### Model Middleware
Sometimes you want your middleware to wrap around the model call itself, rather than the whole node. This lets you build retry logic specific to the LLM, message history compression, PII detection guards, or similar. We support several prebuilt middlewares for the LLM, plus the same kind of decorator API to build your own.

| Decorator | Runs |
|---|---|
| `rt.before_llm` | Once, before each model call, to transform the inputs |
| `rt.after_llm` | Once, after each successful model call|
| `rt.wrap_llm` | Wraps the whole model call. |

```python
--8<-- "docs/scripts/middleware.py:model_middleware_demo"
```

!!! note "Guardrails are Model Middleware"
    Built-in guardrails (PII redaction, length limits, blocked text, ...) are implemented as model middleware under the hood. See [Guardrails](../middleware/guardrails/overview.md).

## Attaching Middleware
You can attach middleware to any node at creation time, or at any time after.

```python
--8<-- "docs/scripts/middleware.py:attach_creation"
```

```python
--8<-- "docs/scripts/middleware.py:attach_after_creation"
```

!!! Note
    `extend_middleware` returns a **new**, immutable `Node` subclass rather than mutating the original. This means any previous references to the node (e.g. `BaseAgent` above) will not have the new middleware attached. Instead you must use the returned reference (`ExtendedAgent` above) going forward.

## Middleware Ordering
A common question when working with middleware is how the ordering is determined. Our API is designed to be as simple as possible: every time you add a middleware to a node, it is added as the outermost layer.

```
Middleware -> Node -> Middleware
```

When adding multiple middleware at once, they run in list order (i.e. index 0 runs first, and is outermost):

```
middleware[0] -> middleware[1] -> Node -> middleware[1] -> middleware[0]
```

```python
--8<-- "docs/scripts/middleware.py:ordering_demo"
```
