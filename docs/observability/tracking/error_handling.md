# Error Handling

Railtracks (RT) provides a comprehensive error handling system designed to give developers clear, actionable feedback when things go wrong. The framework uses a hierarchy of specialized exceptions that help you understand exactly what went wrong and where.

## Error Hierarchy

All Railtracks errors inherit from the base `RTError` class, which provides colored console output and structured error reporting.

```
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
--8<-- "docs/scripts/error_handling.py:llm_dispatch"
```

!!! note "Order your `except` clauses most-specific first"

    `LLMError` is a `NodeInvocationError`. Python takes the first *matching* clause, not the closest one, so putting `except NodeInvocationError` above `except LLMError` makes the second unreachable.

### LLM layer errors

`railtracks.llm` is self-contained and raises its own errors, under two unrelated roots:

```
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

| raised in `railtracks.llm` | surfaces from a node as |
| --- | --- |
| `ProviderTimeoutError` | `LLMTimeoutError` |
| `ProviderRateLimitError` | `LLMRateLimitError` |
| `ProviderAuthenticationError` | `LLMAuthenticationError` |
| `ProviderError` (anything else) | `LLMError` |
| `ToolCreationError` | `NodeInvocationError` with `fatal=True` |

You never have to unwrap anything to find out *what* went wrong: an exhausted retry of timeouts arrives as an `LLMTimeoutError`, whether or not a retry approach was configured.

Because wrapping produces a *new* exception object, `e` is the `LLMError` and `e.__cause__` is the original. The two hierarchies share no ancestor, so `isinstance(e, RetryError)` is always `False`.

## Error Types

### Internally Raised Errors

These errors are automatically raised by Railtracks when issues occur during execution. They provide colored terminal output with debugging information.

- **`NodeCreationError`** - Raised during node setup and validation
- **`NodeInvocationError`** - Raised during node execution (has `fatal` flag)
- **`LLMError`** - Raised during LLM operations (includes `message_history`)
- **`GlobalTimeOutError`** - Raised when execution exceeds timeout
- **`ContextError`** - Raised for [context](../../documentation/advanced/context.md) related issues

All internal errors include helpful debugging notes and formatted error messages to guide troubleshooting.

### User-Raised Errors

**`FatalError`** - The only error type designed for developers to raise manually when encountering unrecoverable situations. When raised within a run it will stop it.

!!! example "Usage"

    ```python
    --8<-- "docs/scripts/error_handling.py:fatal_error"
    ```

### Inspecting LLMError message history

`LLMError` carries the input `MessageHistory` on `err.message_history` so you can inspect it programmatically. `str(err)` and `repr(err)` never embed that history. The exception text shows only a redacted summary like `"N message(s) redacted"`. This keeps conversation contents (which may include PII, credentials, or customer data) out of anything that captures the exception string, such as `logger.exception(...)` or a crash reporter.

!!! danger "Full Message History"
    If you need the full history in a log line for debugging, render it explicitly at the call site:

    ```python
    --8<-- "docs/scripts/error_handling.py:msg_hist"
    ```

## Error Handling Patterns

???+ example "Degrading gracefully inside a node"

    Each `except` narrows the response to what actually failed: retry a slow model,
    switch tiers when rate limited, and give up gracefully on anything else.

    ```python
    --8<-- "docs/scripts/error_handling.py:custom_node"
    ```

???+ example "Basic Error Handling"

    ```python
    --8<-- "docs/scripts/error_handling.py:simple_handling"
    ```

??? example "Comprehensive Error Handling"

    ```python
    --8<-- "docs/scripts/error_handling.py:comprehensive_handling"

    ```

### Error Recovery Strategies

???+ example "Retry with Exponetial Backoff"

    ```python
    --8<-- "docs/scripts/error_handling.py:exp_backoff"
    ```

??? example "Graceful Fallback"

    ```python
    --8<-- "docs/scripts/error_handling.py:fallback"
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
For detailed logging and monitoring strategies, see [Logging](logging.md).


## Debugging Tips

1. **Enable Debug Logging**: Railtracks errors include colored output and debugging notes
2. **Check Error Properties**: Many errors include additional context (notes, message_history, etc.)
3. **Use Message History**: LLMError includes conversation context for debugging
4. **Examine Stack Traces**: RT errors preserve the full stack trace for debugging
5. **Test Error Scenarios**: Write tests that verify your error handling works correctly

The Railtracks error system is designed to fail fast when appropriate, provide clear feedback, and enable robust error recovery strategies.