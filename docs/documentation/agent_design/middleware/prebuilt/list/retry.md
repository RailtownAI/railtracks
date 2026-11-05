# Retry

`Retry` re-runs the wrapped call when it raises a transient error, using a configurable backoff schedule. It is **slot-agnostic**: attach it as node middleware to retry a whole node, as model middleware to retry a single model call, or both.

By default `Retry` retries rate limits and timeouts in every form they take on the way up: litellm's own errors (plus connection and 5xx failures), `ProviderTimeoutError` and `ProviderRateLimitError` (what model middleware sees once the model has translated litellm's errors), and `LLMTimeoutError` and `LLMRateLimitError` (what node middleware sees once they leave an agent node). So the defaults work in both slots, with one gap at node level: connection and 5xx failures leave an agent node as a plain `LLMError`, so a node-level `Retry` only retries them if you add `LLMError` to `retry_on`. Pass your own `retry_on` tuple to replace them. Anything not in the tuple propagates after one attempt, and once every attempt fails `Retry` raises `rt.llm.RetryError` with each attempt's error in `.exception_list`.

Retry layers don't multiply. If the model call already ran out of retries, from `retry_approach=` on the model or a `Retry` in `model_middleware=`, the node's `LLMTimeoutError` or `LLMRateLimitError` has `retry_exhausted` set and a node-level `Retry` lets it through instead of starting over. Three model-level attempts plus `middleware=[Retry(3)]` makes three provider calls, not nine.

## Usage

```python
--8<-- "docs/scripts/prebuilt_middleware.py:retry"
```

Tune the number of attempts, the backoff schedule, and which exceptions to retry:

```python
--8<-- "docs/scripts/prebuilt_middleware.py:retry_configured"
```

!!! note "Ordering"
    Middleware runs outermost-first in list order. Placed before another middleware, `Retry` re-invokes everything inside it on each attempt.
