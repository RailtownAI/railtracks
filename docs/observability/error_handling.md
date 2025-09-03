# 🚨 Error Handling

RailTracks (RT) provides a comprehensive error handling system designed to give developers clear, actionable feedback when things go wrong. The framework uses a hierarchy of specialized exceptions that help you understand exactly what went wrong and where.

## 🏗️ Error Hierarchy

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

## 🎯 Error Types

### 🔧 Internally Raised Errors

These errors are automatically raised by RailTracks when issues occur during execution. All inherit from `RTError` and provide colored terminal output with debugging information.

- **`NodeCreationError`** ⚙️ - Raised during node setup and validation
- **`NodeInvocationError`** ⚡ - Raised during node execution (has `fatal` flag)
- **`LLMError`** 🤖 - Raised during LLM operations (includes `message_history`)
- **`GlobalTimeOutError`** ⏰ - Raised when execution exceeds timeout
- **`ContextError`** 🌐 - Raised for context-related issues

All internal errors include helpful debugging notes and formatted error messages to guide troubleshooting.

### ⚠️ User-Raised Errors

**`FatalError`** 💀 - The only error type designed for developers to raise manually when encountering unrecoverable situations.

**Usage:**
```python
from rt.exceptions import FatalError

def my_critical_function():
    if critical_condition_failed:
        raise FatalError("Critical system state compromised")
```

## 🔄 Error Handling Patterns

### 🔨 Basic Error Handling

```python
import railtracks as rt
from rt.exceptions import NodeInvocationError, LLMError

try:
    result = await rt.call(node, user_input="Tell me about machine learning")
except NodeInvocationError as e:
    if e.fatal:
        # Fatal errors should stop execution
        logger.error(f"Fatal node error: {e}")
        raise
    else:
        # Non-fatal errors can be handled gracefully
        logger.warning(f"Node error (recoverable): {e}")
        # Implement retry logic or fallback
        
except LLMError as e:
    logger.error(f"LLM operation failed: {e.reason}")
    # Maybe retry with different parameters
    # Or fallback to a simpler approach
```

### 🔍 Comprehensive Error Handling

```python
import railtracks as rt
from rt.exceptions import (
    RTError, NodeCreationError, NodeInvocationError, 
    LLMError, GlobalTimeOutError, ContextError, FatalError
)

try:
    # Setup phase
    node = rt.agent_node(
        llm=rt.llm.OpenAI("gpt-4o"),
        system_message="You are a helpful assistant",
    )
    
    # Configure timeout
    rt.set_config(timeout=60.0)
    
    # Execution phase
    result = await rt.call(node, user_input="Explain quantum computing")
    
except NodeCreationError as e:
    # Configuration or setup issue
    logger.error("Node setup failed - check your configuration")
    print(e)  # Shows debugging tips
    
except NodeInvocationError as e:
    # Runtime execution issue
    if e.fatal:
        logger.error("Fatal execution error - stopping")
        raise
    else:
        logger.warning("Recoverable execution error")
        # Implement recovery strategy
        
except LLMError as e:
    # LLM-specific issue
    logger.error(f"LLM error: {e.reason}")
    if e.message_history:
        # Analyze conversation for debugging
        save_debug_history(e.message_history)
        
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
    
except RTError as e:
    # Catch any other RT errors
    logger.error(f"RailTracks error: {e}")
    
except Exception as e:
    # Non-RT errors
    logger.error(f"Unexpected error: {e}")
```

### 🔄 Error Recovery Strategies

#### 🔁 Retry with Backoff

```python
import asyncio
import railtracks as rt
from rt.exceptions import NodeInvocationError, LLMError

async def call_with_retry(node, user_input, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await rt.call(node, user_input=user_input)
        except (NodeInvocationError, LLMError) as e:
            if attempt == max_retries - 1:
                raise  # Last attempt, re-raise
            
            wait_time = 2 ** attempt  # Exponential backoff
            logger.warning(f"Attempt {attempt + 1} failed, retrying in {wait_time}s")
            await asyncio.sleep(wait_time)
```

#### 🛡️ Graceful Degradation

```python
import railtracks as rt
from rt.exceptions import NodeInvocationError

async def call_with_fallback(primary_node, fallback_node, user_input):
    try:
        return await rt.call(primary_node, user_input=user_input)
    except NodeInvocationError as e:
        if not e.fatal:
            logger.info("Primary execution failed, trying fallback")
            return await rt.call(fallback_node, user_input=user_input)
        raise
```

## ✅ Best Practices

### 1. 📝 Handle Errors at the Right Level
- Handle `NodeCreationError` during setup/configuration
- Handle `NodeInvocationError` during execution with appropriate recovery
- Handle `LLMError` with retry logic and fallbacks
- Let `FatalError` bubble up to stop execution

### 2. 📊 Use Error Information
- Check the `fatal` flag on `NodeInvocationError`
- Examine `message_history` in `LLMError` for debugging
- Read the `notes` property for debugging tips

### 3. 🔧 Implement Appropriate Recovery
- Retry transient errors (network issues, rate limits)
- Fallback for recoverable errors
- Fail fast for configuration errors
- Log appropriately for debugging

### 4. 📈 Monitor and Alert
For detailed logging and monitoring strategies, see [Logging](logging.md).

### 5. 🧪 Testing Error Scenarios
```python
import pytest
import railtracks as rt
from rt.exceptions import NodeInvocationError

def test_node_error_handling():
    with pytest.raises(NodeInvocationError) as exc_info:
        # Test code that should raise NodeInvocationError
        pass
    
    assert not exc_info.value.fatal  # Test specific properties
    assert "expected error message" in str(exc_info.value)
```

## 🔍 Debugging Tips

1. **Enable Debug Logging**: RailTracks errors include colored output and debugging notes
2. **Check Error Properties**: Many errors include additional context (notes, message_history, etc.)
3. **Use Message History**: LLMError includes conversation context for debugging
4. **Examine Stack Traces**: RT errors preserve the full stack trace for debugging
5. **Test Error Scenarios**: Write tests that verify your error handling works correctly

The RailTracks error system is designed to fail fast when appropriate, provide clear feedback, and enable robust error recovery strategies.