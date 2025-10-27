# Configuration

Railtracks provides flexible configuration options to customize the behavior of your agent executions. You can control timeouts, logging, error handling, and more through a simple configuration system.

## Configuration Methods

Configuration parameters follow a specific precedence order, allowing you to override settings at different levels:

1. **Session Constructor Parameters** - Highest priority
2. **Global Configuration** (`rt.set_config()`) - Medium priority  
3. **Default Values** - Lowest priority

## Available Configuration Parameters

### Core Execution Settings

- **`timeout`** (`float`): Maximum seconds to wait for a response to your top-level request
- **`end_on_error`** (`bool`): Stop execution when an exception is encountered

### Logging Configuration

- **`logging_setting`** (AllowableLogLevels | None): Level of logging detail.  <br>Here are the `AllowableLogLevels` options:
    - `DEBUG`
    - `INFO`
    - `WARNING`
    - `ERROR`
    - `CRITICAL`
    - `NONE`
- **`log_file`** (`str | os.PathLike | None`): File path for log output (None = no file logging)

### Advanced Settings

- **`context`** (`Dict[str, Any]`): Global context variables for execution
- **`broadcast_callback`** (`Callable`): Callback function for broadcast messages
- **`prompt_injection`** (`bool`): Automatically inject prompts from context variables
- **`save_state`** (`bool`): Save execution state to `.railtracks` directory

## Default Values

```python
# Default configuration values
timeout = 150.0                   # seconds
end_on_error = False              # continue on errors
logging_setting = "INFO"       # standard logging level
log_file = None                   # no file logging
broadcast_callback = None         # no broadcast callback
prompt_injection = True           # enable prompt injection
save_state = True                 # save execution state
```

## Method 1: Session Constructor

Configure settings when creating a session for your agent execution:

```python
import railtracks as rt

# Configure for a partiular session execution
with rt.session(
    timeout=300.0,
    end_on_error=True,
    logging_setting="DEBUG",
    log_file="execution.log",
    prompt_injection=False,
    save_state=False,
    context={"user_name": "Alice", "environment": "production"}
    ):
    response = await rt.call(
        my_agent,
        "Hello world!",
    )
```

## Method 2: Global Configuration

Set configuration globally using `rt.set_config()`. This must be called **before** any `rt.call()`:

```python
import railtracks as rt

# Set global configuration
rt.set_config(
    timeout=200.0,
    logging_setting="DEBUG",
    log_file="app_logs.log",
    end_on_error=True,
    context={"app_version": "1.2.3"}
)

# Now all subsequent calls will use these settings
response1 = await rt.call(agent1, "First request")
response2 = await rt.call(agent2, "Second request")
```

## Configuration Precedence

When the same parameter is set in multiple places, Railtracks uses this priority order:

```python
import railtracks as rt

# 1. Set global config (medium priority)
rt.set_config(timeout=100.0, logging_setting="INFO")

# 2. Session overrides global config (highest priority)
with rt.session(
    timeout=300.0,        # This overrides the global timeout=100.0
    end_on_error=True     # This uses session-level setting
    # logging_setting not specified, so uses global "INFO"
):
    response = await rt.call(
        my_agent,
        "Hello!",
    )

# Final effective configuration:
# - timeout: 300.0 (from session constructor)
# - end_on_error: True (from session constructor)  
# - logging_setting: "INFO" (from global config)
# - All other parameters use default values
```

## Best Practices

### Development vs Production

```python
import railtracks as rt
import os

# Configure based on environment
if os.getenv("ENVIRONMENT") == "production":
    rt.set_config(
        timeout=300.0,
        logging_setting="INFO",
        log_file="production.log",
        end_on_error=False,
        save_state=True
    )
else:
    rt.set_config(
        timeout=60.0,
        logging_setting="DEBUG", 
        log_file="debug.log",
        end_on_error=True,
        save_state=False
    )
```

### Debugging Configuration

```python
import railtracks as rt

# Enhanced debugging setup
rt.set_config(
    logging_setting="DEBUG",
    log_file="debug_session.log",
    end_on_error=True,           # Stop on first error
    save_state=True,             # Save state for inspection
)

def debug_callback(message: str):
    print(f"Broadcast: {message}")

with rt.session(
    broadcast_callback=debug_callback,
):
    response = await rt.call(
        my_agent,
        "Debug this workflow",
    )
```
## Important Notes

- `rt.set_config()` must be called **before** any agent execution
- Session constructor parameters always take highest precedence
- Configuration is global and affects all subsequent agent calls
- Default values are used for any unspecified parameters