# Retry

`Retry` re-runs the wrapped call when it raises a transient error, using a configurable backoff schedule. It is **slot-agnostic**: attach it as node middleware to retry a whole node, as model middleware to retry a single model call, or both.

By default `Retry` retries transient LLM provider errors (rate limits, timeouts, connection failures), plus `DecisionTimeoutError` and `DecisionRateLimitError` from decision nodes. Pass your own `retry_on` tuple to replace these defaults. Non-retryable errors propagate unchanged after one attempt. When retryable errors exhaust the attempts, `Retry` raises `RetryError`, whose `.exception_list` contains every attempt's error. At a decision node's boundary, a `RetryError` ending in a `DecisionModelError` is translated to a fresh error of that decision-error subclass, preserving the provider cause and adding a "Gave up after N attempts." note. Function and agent nodes retain `RetryError` on exhaustion, including function nodes that call a decision node.

Retrying at multiple call boundaries multiplies attempts. A model configured for three attempts inside a decision node with `Retry(3)` can make nine provider calls. A function node with `Retry(3)` calling a decision node with `Retry(3)` can also make nine. Use one retry layer for a single attempt budget.

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
