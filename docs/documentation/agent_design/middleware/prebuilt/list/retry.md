# Retry

`Retry` re-runs the wrapped call when it raises a transient error, using a configurable backoff schedule. It is **slot-agnostic**: attach it as node middleware to retry a whole node, as model middleware to retry a single model call, or both.

By default `Retry` retries transient LLM provider errors (rate limits, timeouts, connection failures), plus `DecisionTimeoutError` and `DecisionRateLimitError` from decision nodes. Pass your own `retry_on` tuple to replace these defaults. Non-retryable errors propagate unchanged after one attempt.

When decision errors exhaust the attempts, `Retry` raises a fresh error of the last attempt's `DecisionModelError` subclass, preserving the provider cause and existing attributes and notes, and adding a "Gave up after N attempts." note. Its `.retry_exhausted` flag is `True`, and `.retry_errors` contains the failed attempts. This applies wherever the decision error reaches `Retry`, including a function that calls a decision node, and lets middleware outside `Retry` catch `DecisionModelError` for a fallback. Other retryable errors raise `RetryError` on exhaustion, with the attempts in `.exception_list`.

Outer retry layers propagate errors marked `.retry_exhausted` unchanged, even with `retry_on=(Exception,)`. This prevents model-level `retry_approach` plus node-level `Retry`, or a function's `Retry` around a decision node's `Retry`, from restarting an exhausted budget. An inner budget of three attempts makes three provider calls on failure; outer layers add neither attempts nor exhaustion notes.

The new defaults also affect a function with `Retry()` calling a decision node without its own retry middleware. A nested decision timeout or rate limit now retries the function instead of propagating after the first attempt. Once exhausted, the matching decision-error subclass reaches the caller. An already-exhausted model-level error passes through without retrying the function.

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
