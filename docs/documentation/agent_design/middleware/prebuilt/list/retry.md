# Retry

`Retry` re-runs the wrapped call when it raises a transient error, using a configurable backoff schedule. It is **slot-agnostic**: attach it as node middleware to retry a whole node, as model middleware to retry a single model call, or both.

By default `Retry` retries the transient errors a model call raises: rate limits, timeouts and connection failures. Pass your own `retry_on` tuple to replace them. Anything not in the tuple propagates after one attempt, and once every attempt fails `Retry` raises `rt.llm.RetryError` with each attempt's error in `.exception_list`.

On an agent node, put `Retry` in `model_middleware=`. Each attempt then repeats only the model call that failed. As node middleware, each attempt re-runs the whole agent: tools it already called run again, and with `rt.astream` the caller receives the text streamed before the failure a second time. The defaults don't match the errors an agent node raises (`LLMTimeoutError`, `LLMRateLimitError`), so node-level retry on an agent only happens if you pass them in `retry_on` yourself.

Retry layers don't multiply. When `retry_approach=` on the model runs out of attempts it raises `RetryError`, which a `Retry` in `model_middleware=` doesn't retry by default. Three attempts from `retry_approach=` plus `model_middleware=[Retry(3)]` makes three provider calls, not nine.

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
