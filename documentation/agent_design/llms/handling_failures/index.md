# Handling LLM Failures

LLM failures are inevitable. In your agent design you must handle these failures accordingly. Railtracks gives you the tooling to handle them gracefully.

## Types of Failures

LLM failures fall into two categories, and the right handling differs between them:

1. **Retryable Failures**: Known anticipated errors you can recover from. Including, rate limits (`429`), timeouts, transient server errors. Safe to retry with backoff.
1. **Fatal Failures**: Unexpected errors that retrying won't fix — unhandled exceptions, malformed responses, or hard API errors. These should fail fast and surface to the caller.

## Railtracks Tooling for Retries

Pass a `RetryApproach` to your LLM and it handles retry logic automatically. The internal logic will handle the difference between errors where you should retry on vs. not. Here's an example using jittered exponential backoff:

```python
import railtracks as rt

exponentialRetry = rt.llm.retries.ExponentialRetry(
    max_tries=5,
    base=2.0,  # delay will be 2^attempt seconds
    jitter=True,  # add random jitter to avoid thundering herd
)
# Now pass in that expoential configuration into your llm. 
rt.llm.OpenAILLM(
    model_name="gpt-6-luna",
    retry_approach=exponentialRetry,
)
```

Railtracks Recommendation

Jittered Exponential Backoff is the industry standard and should be used in nearly all cases.

Custom Retry Logic

If you want to implement custom retry logic, you can do so by creating a class that inherits from `RetryApproach` and implementing the `call_with_retry` method. Here's an example of a custom retry approach that implements a fixed retry strategy:

```python
import railtracks as rt

class CustomRetry(rt.llm.retries.RetryApproach):
    @classmethod
    def approach_name(cls) -> str:
        return "custom"

    def _compute_delay(self, attempt: int) -> float:
        # implement your custom retry logic here. For example, you could do a quadratic backoff etc. For more complex logic, please create a new issue or reach out directly to the RailTracks team.
        return 1
```
