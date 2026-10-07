# Error Handling

Railtracks (RT) provides a comprehensive error handling system designed to give developers clear, actionable feedback when things go wrong. The framework uses a hierarchy of specialized exceptions that help you understand exactly what went wrong and where.

## Error Hierarchy

All Railtracks errors inherit from the base `RTError` class, which provides colored console output and structured error reporting.

```text
RTError (base)
├── NodeCreationError
├── NodeInvocationError               "a node terminated unexpectedly"
│   ├── LLMError                      ...because the LLM layer failed
│   │   ├── LLMTimeoutError           ......the model did not answer in time
│   │   ├── LLMRateLimitError         ......rate or quota limit hit
│   │   └── LLMAuthenticationError    ......bad credentials; do not retry
│   └── GuardrailBlockedError         ...because a guardrail blocked it
├── GlobalTimeOutError
├── ContextError
└── FatalError
```

`NodeInvocationError` tells you *that* a node terminated; its subclasses tell you *why*. Every level is a plain `except` clause, so you handle only as much detail as you care about:

```python
from railtracks.exceptions import (
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMError,
    NodeInvocationError,
)

try:
    result = await rt.call(func, "Summarise this document")

except LLMTimeoutError:
    # The model did not answer in time -- usually worth another attempt.
    result = await rt.call(func, "Summarise this document")

except LLMRateLimitError:
    # Back off rather than hammering the provider.
    await asyncio.sleep(30)
    result = await rt.call(func, "Summarise this document")

except LLMAuthenticationError:
    # Retrying will never help; this is a configuration problem.
    logger.critical("Check your API key")
    raise

except LLMError as e:
    # Any other LLM failure. The provider's original error is on __cause__.
    logger.error(f"LLM failed: {e.reason} (cause: {e.__cause__!r})")
    raise

except NodeInvocationError as e:
    # The node died for a non-LLM reason -- config, guardrail, structure.
    logger.error(f"Node failed: {e}")
    raise
```

Order your `except` clauses most-specific first

`LLMError` is a `NodeInvocationError`. Python takes the first *matching* clause, not the closest one, so putting `except NodeInvocationError` above `except LLMError` makes the second unreachable.

### LLM layer errors

`railtracks.llm` is self-contained and raises its own errors, under two unrelated roots:

```text
ProviderError                    talking to a model provider
├── ProviderTimeoutError
├── ProviderRateLimitError
├── ProviderAuthenticationError
├── ModelError
│   ├── FunctionCallingNotSupportedError
│   └── UnsupportedHyperparameterError
├── ModelNotFoundError
└── RetryError

ToolCreationError        defining a tool -- a bug in your code, not a provider failure
```

You only see these when calling a model **directly**. Inside a node they are translated once, at the boundary, and the original stays reachable on `__cause__`:

| raised in `railtracks.llm`      | surfaces from a node as                 |
| ------------------------------- | --------------------------------------- |
| `ProviderTimeoutError`          | `LLMTimeoutError`                       |
| `ProviderRateLimitError`        | `LLMRateLimitError`                     |
| `ProviderAuthenticationError`   | `LLMAuthenticationError`                |
| `ProviderError` (anything else) | `LLMError`                              |
| `ToolCreationError`             | `NodeInvocationError` with `fatal=True` |

You never have to unwrap anything to find out *what* went wrong: an exhausted retry of timeouts arrives as an `LLMTimeoutError`, whether or not a retry approach was configured.

Because wrapping produces a *new* exception object, `e` is the `LLMError` and `e.__cause__` is the original. The two hierarchies share no ancestor, so `isinstance(e, RetryError)` is always `False`.

## Error Types

### Internally Raised Errors

These errors are automatically raised by Railtracks when issues occur during execution. They provide colored terminal output with debugging information.

- **`NodeCreationError`** - Raised during node setup and validation
- **`NodeInvocationError`** - Raised during node execution (has `fatal` flag)
- **`LLMError`** - Raised during LLM operations (includes `message_history`)
- **`GlobalTimeOutError`** - Raised when execution exceeds timeout
- **`ContextError`** - Raised for [context](https://docs.railtracks.org/documentation/advanced/context/index.md) related issues

All internal errors include helpful debugging notes and formatted error messages to guide troubleshooting.

### User-Raised Errors

**`FatalError`** - The only error type designed for developers to raise manually when encountering unrecoverable situations. When raised within a run it will stop it.

Usage

```python
def critical_function():
    from railtracks.exceptions import FatalError

    raise FatalError("A critical error occurred.")
```

### Inspecting LLMError message history

`LLMError` carries the input `MessageHistory` on `err.message_history` so you can inspect it programmatically. `str(err)` and `repr(err)` never embed that history. The exception text shows only a redacted summary like `"N message(s) redacted"`. This keeps conversation contents (which may include PII, credentials, or customer data) out of anything that captures the exception string, such as `logger.exception(...)` or a crash reporter.

Full Message History

If you need the full history in a log line for debugging, render it explicitly at the call site:

```python
from railtracks.exceptions import LLMError

try:
    ...
except LLMError as err:
    logger.error("LLM call failed: %s", err.format_verbose())
    # or route err.message_history wherever your data-handling policy allows
```

## Error Handling Patterns

Degrading gracefully inside a node

Each `except` narrows the response to what actually failed: retry a slow model, switch tiers when rate limited, and give up gracefully on anything else.

```python
import railtracks as rt
from railtracks.exceptions import LLMRateLimitError, LLMTimeoutError, LLMError

CheapAgent = rt.agent_node(llm=rt.llm.OpenAILLM("gpt-6-luna"), name="Cheap")
StrongAgent = rt.agent_node(llm=rt.llm.AnthropicLLM("claude-sonnet-5-5"), name="Strong")


@rt.function_node
async def summarise(user_input: str) -> str:
    """Summarise text, degrading gracefully as things go wrong."""
    try:
        return (await rt.call(CheapAgent, user_input)).content

    except LLMTimeoutError:
        # Slow model, not a broken one -- a second attempt often lands.
        return (await rt.call(CheapAgent, user_input)).content

    except LLMRateLimitError:
        # Rate limited on the cheap tier; spend money instead of waiting.
        return (await rt.call(StrongAgent, user_input)).content

    except LLMError as e:
        # Anything else from the LLM: give the caller something usable.
        logger.warning("Summarisation failed: %s (cause: %r)", e.reason, e.__cause__)
        return "Summary unavailable."
```

Basic Error Handling

```python
from railtracks.exceptions import NodeInvocationError, LLMError
import logging

logger = logging.getLogger(__name__)

try:
    result = await rt.call(func, "Tell me about machine learning")

# LLMError is a NodeInvocationError, so it must come first -- Python takes the
# first *matching* clause, not the most specific one.
except LLMError as e:
    logger.error(f"LLM operation failed: {e.reason}")
    # Maybe retry with different parameters, or fall back to a simpler approach

except NodeInvocationError as e:
    if e.fatal:
        # Fatal errors should stop execution
        logger.error(f"Fatal node error: {e}")
        raise
    else:
        # Non-fatal errors can be handled gracefully
        logger.warning(f"Node error (recoverable): {e}")
        # Implement retry logic or fallback
```

Comprehensive Error Handling

```python
from railtracks.exceptions import (
    NodeCreationError,
    NodeInvocationError,
    LLMError,
    GlobalTimeOutError,
    ContextError,
    FatalError,
)

try:
    # Setup phase
    Assistant = rt.agent_node(
        llm=rt.llm.OpenAILLM("gpt-6-luna"),
        system_message="You are a helpful assistant",
    )

    # Configure timeout
    rt.set_config(timeout=60.0)

    # Execution phase
    result = await rt.call(Assistant, user_input="Explain quantum computing")

except NodeCreationError as e:
    # Configuration or setup issue
    logger.error("Node setup failed - check your configuration")
    print(e)  # Shows debugging tips

except LLMError as e:
    # LLM-specific issue. Listed above NodeInvocationError because it is one.
    logger.error(f"LLM error: {e.reason}")
    if e.message_history:
        # Analyze conversation for debugging
        pass

except NodeInvocationError as e:
    # Runtime execution issue that did not come from the LLM
    if e.fatal:
        logger.error("Fatal execution error - stopping")
        raise
    else:
        logger.warning("Recoverable execution error")
        # Implement recovery strategy

except GlobalTimeOutError as e:
    # Execution took too long
    logger.error(f"Execution timed out after {e.timeout}s")
    # Maybe increase timeout or optimize graph

except ContextError as e:
    # Context management issue
    logger.error("Context error - check your context setup")
    print(e)  # Shows debugging tips

except FatalError as e:
    # User-defined critical error
    logger.critical(f"Fatal error: {e}")
    # Implement emergency shutdown procedures

except Exception as e:
    # Non-RT errors
    logger.error(f"Unexpected error: {e}")
```

### Error Recovery Strategies

Retry with Exponetial Backoff

```python
import asyncio
import railtracks as rt
from railtracks.exceptions import LLMRateLimitError, LLMTimeoutError

# Retry only what is actually transient. A malformed tool or a bad API key fails the
# same way every time, so retrying those just delays the error you need to see.
RETRYABLE = (LLMTimeoutError, LLMRateLimitError)


async def call_with_retry(node, user_input, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await rt.call(node, user_input=user_input)
        except RETRYABLE as e:
            if attempt == max_retries - 1:
                raise  # Last attempt, re-raise

            wait_time = 2**attempt  # Exponential backoff
            logger.warning(f"{type(e).__name__}, retrying in {wait_time}s")
            await asyncio.sleep(wait_time)
```

Graceful Fallback

```python
from railtracks.exceptions import LLMError


async def call_with_fallback(primary_node, fallback_node, user_input):
    try:
        return await rt.call(primary_node, user_input=user_input)
    except LLMError:
        # The model let us down; a different one may not.
        logger.info("Primary execution failed, trying fallback")
        return await rt.call(fallback_node, user_input=user_input)
```

## Best Practices

### 1. Handle Errors at the Right Level

- Handle `NodeCreationError` during setup/configuration
- Handle `NodeInvocationError` during execution with appropriate recovery
- Handle `LLMError` with retry logic and fallbacks
- Let `FatalError` bubble up to stop execution

### 2. Use Error Information

- Check the `fatal` flag on `NodeInvocationError`
- Examine `message_history` in `LLMError` for debugging
- Read the `notes` property for debugging tips

### 3. Implement Appropriate Recovery

- Retry transient errors (network issues, rate limits)
- Fallback for recoverable errors
- Fail fast for configuration errors
- Log appropriately for debugging

### 4. Monitor and Alert

For detailed logging and monitoring strategies, see [Logging](https://docs.railtracks.org/observability/tracking/logging/index.md).

## Debugging Tips

1. **Enable Debug Logging**: Railtracks errors include colored output and debugging notes
1. **Check Error Properties**: Many errors include additional context (notes, message_history, etc.)
1. **Use Message History**: LLMError includes conversation context for debugging
1. **Examine Stack Traces**: RT errors preserve the full stack trace for debugging
1. **Test Error Scenarios**: Write tests that verify your error handling works correctly

The Railtracks error system is designed to fail fast when appropriate, provide clear feedback, and enable robust error recovery strategies.
