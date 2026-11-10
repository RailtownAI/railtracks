# Retry

`Retry` re-runs the wrapped call when it raises a transient error, using a configurable backoff schedule. It is **slot-agnostic**: attach it as node middleware to retry a whole node, as model middleware to retry a single model call, or both.

By default `Retry` only retries the transient LLM provider errors (rate limits, timeouts, connection failures). For node-level use, pass your own `retry_on` tuple.

## Usage

```python
import railtracks as rt
from railtracks.prebuilt.middleware import Retry

# Retry is slot-agnostic: use it as node middleware, model middleware, or both.
RetryAgent = rt.agent_node(
    name="retry-demo",
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    middleware=[Retry(3)],  # retry the whole node call
    model_middleware=[Retry(3)],  # retry each raw model call
)
```

Tune the number of attempts, the backoff schedule, and which exceptions to retry:

```python
from railtracks.llm.retries import ExponentialRetry

# Tune the number of attempts, the backoff schedule, and which errors to retry.
picky_retry = Retry(
    approach=ExponentialRetry(max_tries=5),
    retry_on=(TimeoutError, ConnectionError),
)
```

Ordering

Middleware runs outermost-first in list order. Placed before another middleware, `Retry` re-invokes everything inside it on each attempt.
