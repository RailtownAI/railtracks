# Custom Middleware

The middleware system is designed to support the custom creation of middleware to fit your needs. Each decorator below wraps a plain function into a `Middleware` object. Node-level decorators can be passed to `middleware=` on either `rt.agent_node` or `rt.function_node`. Model-level decorators can only be passed to `model_middleware=` on `rt.agent_node`. A `function_node` never calls a model, so it has no `model_middleware=` slot (the parameter doesn't exist on `function_node`, so passing one is a type/argument error, not a silent no-op).

| Decorator      | Scope | Runs                                                                         |
| -------------- | ----- | ---------------------------------------------------------------------------- |
| `rt.wrap_node` | Node  | Wraps the whole node call. You decide if/how many times the inner call runs  |
| `rt.post_node` | Node  | Once, after the node completes successfully (skipped if it raises)           |
| `rt.wrap_llm`  | Model | Wraps the whole model call. You decide if/how many times the inner call runs |
| `rt.pre_llm`   | Model | Once, before each model call, to transform the inputs                        |
| `rt.post_llm`  | Model | Once, after each successful model call                                       |

`wrap_node` and `wrap_llm` are the general-purpose forms. Every other decorator is a thin convenience built on top of one of them (`post_node` and `post_llm` only get to run the inner call once and act on its result; `pre_llm` only gets to transform the inputs before the inner call runs).

`wrap_node` / `wrap_llm` functions must be `async def`

`wrap_node` and `wrap_llm` re-invoke the inner call directly, so the function you decorate must be defined with `async def`. A plain `def` raises `TypeError` immediately for `wrap_node`, or fails with a confusing "can't be used in 'await' expression" error at call time for `wrap_llm`. `post_node`, `pre_llm`, and `post_llm` are more forgiving: they accept either a plain `def` or an `async def`.

## Node middleware

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

## Model middleware

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
