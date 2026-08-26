# Error Handling

Railtracks (RT) provides a comprehensive error handling system designed to give developers clear, actionable feedback when things go wrong. The framework uses a hierarchy of specialized exceptions that help you understand exactly what went wrong and where.

## Error Hierarchy

All Railtracks errors inherit from the base `RTError` class, which provides colored console output and structured error reporting.

```
RTError (base)
├── NodeCreationError
├── NodeInvocationError          "a node terminated unexpectedly"
│   ├── LLMError                 ...because the LLM layer failed
│   └── GuardrailBlockedError    ...because a guardrail blocked it
├── GlobalTimeOutError
├── ContextError
└── FatalError
```

`NodeInvocationError` tells you *that* a node terminated; its subclasses tell you *why*. That lets you handle both questions in one place:

```python
try:
    result = await rt.call(my_agent, "hello")
except LLMError as e:
    retry_with_fallback_model(e.message_history)
except NodeInvocationError as e:
    # A node died for some other reason -- config, guardrail, structure.
    report(e)
```

!!! note "Order your `except` clauses most-specific first"

    `LLMError` is a `NodeInvocationError`. Python takes the first *matching* clause, not the closest one, so putting `except NodeInvocationError` above `except LLMError` makes the second unreachable.

### LLM package errors

The `railtracks.llm` package is self-contained and does not import from the rest of Railtracks, so it raises its own errors rooted at `RTLLMError`:

```
RTLLMError (base)
├── RetryError
├── ModelError
│   ├── FunctionCallingNotSupportedError
│   └── UnsupportedHyperparameterError
├── ModelNotFoundError
└── ToolCreationError
```

You only see these when calling a model **directly**. Inside a node, they are translated once at the boundary into `LLMError`, and the original stays reachable on `__cause__`:

```python
except LLMError as e:
    if isinstance(e.__cause__, RetryError):
        ...  # the model was retried and still failed
```

`RTLLMError` is deliberately **not** an `RTError` -- the two hierarchies are independent, which is what keeps the `llm` package standalone.

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

## Error Handling Patterns

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