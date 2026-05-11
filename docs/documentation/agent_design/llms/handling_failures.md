# Handling LLM Failures
LLM failures are inevitable. In your agent design you must handle these failures accoridingly Railtracks gives you the tooling to handle them gracefully.

## Types of Failures
LLM failures fall into two categories, and the right handling differs between them:

1. **Retryable Failures**: Known, anticipated errors you can recover from. Including, rate limits (`429`), timeouts, transient server errors. Safe to retry with backoff.

2. **Fatal Failures**: Unexpected errors that retrying won't fix — unhandled exceptions, malformed responses, or hard API errors. These should fail fast and surface to the caller.

## Railtracks Tooling for Retries
Pass a `RetryApproach` to your LLM and it handles retry logic automatically. The internal logic will handle the difference between errors where you should retry on vs. not. Here's an example using `ExponentialBackoffRetry`:

```python
--8<-- "docs/scripts/documentation/retries.py:exponential_backoff"
```

!!! tip "Railtracks Recommendation"
    Jittered Exponential Backoff is the industry standard and should be used in nearly all cases. 

???- tip "Custom Retry Logic"
    If you want to implement custom retry logic, you can do so by creating a class that inherits from `RetryApproach` and implementing the `call_with_retry` method. Here's an example of a custom retry approach that implements a fixed retry strategy:
    ```python
    --8<-- "docs/scripts/documentation/retries.py:make_your_own"
    ```