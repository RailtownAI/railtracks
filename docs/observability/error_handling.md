# Error Handling

RailTracks (RT) provides a comprehensive error handling system designed to give developers clear, actionable feedback when things go wrong. The framework uses a hierarchy of specialized exceptions that help you understand exactly what went wrong and where.

## Error Hierarchy

All RailTracks errors inherit from the base `RTError` class, which provides colored console output and structured error reporting.

```
RTError (base)
├── NodeCreationError
├── NodeInvocationError
├── LLMError
├── GlobalTimeOutError
├── ContextError
└── FatalError
```

## Error Types

### Internally Raised Errors

These errors are automatically raised by RailTracks when issues occur during execution. All inherit from `RTError` and provide colored terminal output with debugging information.

- **`NodeCreationError`** - Raised during node setup and validation
- **`NodeInvocationError`** - Raised during node execution (has `fatal` flag)
- **`LLMError`** - Raised during LLM operations (includes `message_history`)
- **`GlobalTimeOutError`** - Raised when execution exceeds timeout
- **`ContextError`** - Raised for [context](../advanced_usage/context.md) related issues

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

1. **Enable Debug Logging**: RailTracks errors include colored output and debugging notes
2. **Check Error Properties**: Many errors include additional context (notes, message_history, etc.)
3. **Use Message History**: LLMError includes conversation context for debugging
4. **Examine Stack Traces**: RT errors preserve the full stack trace for debugging
5. **Test Error Scenarios**: Write tests that verify your error handling works correctly

The RailTracks error system is designed to fail fast when appropriate, provide clear feedback, and enable robust error recovery strategies.