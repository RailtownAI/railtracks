# Middleware

Middleware in Railtracks is a function that wraps a node's call, letting you add behavior around it without touching the node itself. Concretely, middleware can do things like:

- Log inputs and outputs
- Handle automatic retries
- PII detection and redaction
- Unwanted Question rejection

Middleware composes: attach several to the same node and they run as nested layers around the call. Below is a simple example of adding a retry middleware to a flow.

```python
import railtracks as rt


@rt.wrap_node
async def retry(call, *args, **kwargs):
    """Retry the inner call up to 3 times."""
    last = None
    for _ in range(3):
        try:
            return await call(*args, **kwargs)
        except Exception as e:
            last = e

    raise RuntimeError(f"All retries exhausted: {last}") from last

# you can add the middleware to a node at creation time.
RetryAgent = rt.agent_node(name="Agent", llm=rt.llm.OpenAILLM("gpt-6-luna"), middleware=[retry])
```

## Prebuilt Middleware

We provide a suite of prebuilt middleware for common use cases. Check out the complete list of [prebuilt middleware](https://docs.railtracks.org/documentation/agent_design/middleware/prebuilt/overview/index.md). For custom creation of middleware you can use our guide to building your own [custom middleware](https://docs.railtracks.org/documentation/agent_design/middleware/custom/index.md).

## Types of Middleware

### Node Middleware

Most middleware will wrap an entire node or function call, including `rt.function_node`. Common examples include logging, retry logic, [HIL verification](https://docs.railtracks.org/documentation/agent_design/middleware/verifiers/overview/index.md), rate limiting, caching, and more. Outside of what we supply, you can create your own with a small decorator API.

| Decorator      | Runs                                                                        |
| -------------- | --------------------------------------------------------------------------- |
| `rt.wrap_node` | Wraps the whole node call; you decide if/how many times the inner call runs |
| `rt.post_node` | Once, after the node completes successfully (skipped if the node raises)    |

`rt.wrap_node` is the general-purpose form. The retry example above is built on it. `rt.post_node` is a narrower convenience for the common "do something with the result and pass it through" case:

```python
@rt.post_node
def log_result(result):
    print("node finished:", result)
    return result


@rt.wrap_node
async def log_result_async(call, *args, **kwargs):
    result = await call(*args, **kwargs)
    print("node finished:", result)
    return result
```

The same middleware attaches to a `function_node` exactly the same way, via `middleware=`:

```python
# The same middleware works unchanged on a function_node. Only the node-level
# `middleware=` slot applies, since a function node never calls a model.
@rt.function_node(middleware=[retry])
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b
```

### Model Middleware

Sometimes you want your middleware to wrap around the model call itself, rather than the whole node. This lets you build retry logic specific to the LLM, message history compression, PII detection guards, or similar. Model middleware only applies to `rt.agent_node`. A `function_node` never calls a model, so it has no `model_middleware=` slot to attach to. We support several prebuilt middlewares for the LLM, plus the same kind of decorator API to build your own.

| Decorator     | Runs                                                  |
| ------------- | ----------------------------------------------------- |
| `rt.pre_llm`  | Once, before each model call, to transform the inputs |
| `rt.post_llm` | Once, after each successful model call                |
| `rt.wrap_llm` | Wraps the whole model call.                           |

```python
@rt.pre_llm
def print_message(message_history: rt.llm.MessageHistory, schema, tools):
    print(message_history)
    return message_history, schema, tools


@rt.post_llm
def print_response(response: rt.llm.Response):
    print(response.message)
    return response


@rt.wrap_llm
async def periodic_failure(llm_call, message_history, schema, tools):
    import random

    if random.random() < 0.5:
        raise Exception("Random failure")
    return await llm_call(message_history, schema, tools)
```

`wrap_node` / `wrap_llm` functions must be `async def`

`wrap_node` and `wrap_llm` re-invoke the inner call directly, so the function you decorate must be defined with `async def`. A plain `def` raises `TypeError` immediately for `wrap_node`, or fails with a confusing "can't be used in 'await' expression" error at call time for `wrap_llm`. `post_node`, `pre_llm`, and `post_llm` are more forgiving: they accept either a plain `def` or an `async def`.

Guardrails are Model Middleware

Built-in guardrails (PII redaction, length limits, blocked text, ...) are implemented as model middleware under the hood. See [Guardrails](https://docs.railtracks.org/documentation/agent_design/middleware/guardrails/overview/index.md).

## Attaching Middleware

You can attach middleware to any node at creation time, or at any time after.

```python
CreationTimeAgent = rt.agent_node(
    name="Agent",
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    middleware=[retry, log_result],  # runs once per agent call
    model_middleware=[print_message, print_response],  # runs once per model call
)
```

```python
BaseAgent = rt.agent_node(name="Agent", llm=rt.llm.OpenAILLM("gpt-6-luna"))

ExtendedAgent = rt.couple(BaseAgent, middleware=[retry, log_result])
```

Note

`couple` returns a **new**, immutable `Node` subclass rather than mutating the original. This means any previous references to the node (e.g. `BaseAgent` above) will not have the new middleware attached. Instead you must use the returned reference (`ExtendedAgent` above) going forward.

## Middleware Ordering

A common question when working with middleware is how the ordering is determined. Our API is designed to be as simple as possible: every time you add a middleware to a node, it is added as the outermost layer.

```text
Middleware -> Node -> Middleware
```

When adding multiple middleware in one call, they run in list order (i.e. index 0 runs first, and is outermost):

```text
middleware[0] -> middleware[1] -> Node -> middleware[1] -> middleware[0]
```

```python
@rt.wrap_node
async def outer(call, *args, **kwargs):
    print("outer: before")
    result = await call(*args, **kwargs)
    print("outer: after")
    return result


@rt.wrap_node
async def inner(call, *args, **kwargs):
    print("inner: before")
    result = await call(*args, **kwargs)
    print("inner: after")
    return result


OrderedAgent = rt.agent_node(
    name="Agent", llm=rt.llm.OpenAILLM("gpt-6-luna"), middleware=[outer, inner]
)
# calling OrderedAgent prints, in order:
#   outer: before
#   inner: before
#   inner: after
#   outer: after
```

The same "outermost" rule applies when you call `couple()` more than once on the same node: each call's middleware wraps *everything* attached so far, so the most recently coupled middleware ends up outermost:

```python
# couple() adds its middleware as the new outermost layer, so calling it twice
# nests in reverse call order: whatever you couple() last wraps everything
# coupled before it, regardless of what the middleware happens to be named.
StepOne = rt.couple(BaseAgent, middleware=[outer])
StepTwo = rt.couple(StepOne, middleware=[inner])
# calling StepTwo prints, in order:
#   inner: before
#   outer: before
#   outer: after
#   inner: after
```
