# Retry

`Retry` re-runs the wrapped call when it raises a transient error, using a configurable backoff schedule. It is **slot-agnostic**: attach it as node middleware to retry a whole node, as model middleware to retry a single model call, or both.

By default `Retry` retries transient LLM provider errors (rate limits, timeouts, connection failures), plus `DecisionTimeoutError` and `DecisionRateLimitError` from decision nodes. Pass your own `retry_on` tuple to replace these defaults. If retries run out, the last decision-node error is re-raised with a `RetryError` cause containing every attempt's error in `.exception_list`. Other failures raise `RetryError`.

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
