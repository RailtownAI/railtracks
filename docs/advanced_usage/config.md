# Configuration

Railtracks provides flexible configuration options to customize the behavior of your agent executions. You can control timeouts, error handling, and more through a simple configuration system. Logging is configured separately via `rt.enable_logging()` at application startup (see [Logging](../observability/tracking/logging.md)).

## Configuration Methods

Configuration parameters follow a specific precedence order, allowing you to override settings at different levels:

1. **Session Constructor Parameters** - Highest priority
2. **Global Configuration** (`rt.set_config()`) - Medium priority  
3. **Default Values** - Lowest priority

## Available Configuration Parameters

### Core Execution Settings

- **`timeout`** (`float`): Maximum seconds to wait for a response to your top-level request
- **`end_on_error`** (`bool`): Stop execution when an exception is encountered

### Advanced Settings

- **`context`** (`Dict[str, Any]`): Global context variables for execution
- **`broadcast_callback`** (`Callable | dict[str, Callable]`): Passive listener (or per-channel dict) for one-off `rt.broadcast` events
- **`stream_callback`** (`Callable | dict[str, Callable]`): Passive listener (or per-channel dict) for `rt.broadcast_stream` chunks (LLM tokens included); never enables streaming
- **`prompt_injection`** (`bool`): Automatically inject prompts from context variables
- **`save_state`** (`bool`): Save execution state to the `.railtracks` data directory (see [Data directory resolution](#data-directory-railtracks) below)

## Default Values

```python
# Default configuration values
timeout = 150.0                   # seconds
end_on_error = False              # continue on errors
broadcast_callback = None         # no event listener
stream_callback = None            # no stream-chunk listener
prompt_injection = True           # enable prompt injection
save_state = True                 # save execution state
```

## Method 1: Session Constructor

Configure settings when creating a session for your agent execution:

```python
import railtracks as rt

# Configure for a particular session execution
with rt.session(
    timeout=300.0,
    end_on_error=True,
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
rt.set_config(timeout=100.0)

# 2. Session overrides global config (highest priority)
with rt.session(
    timeout=300.0,        # This overrides the global timeout=100.0
    end_on_error=True     # This uses session-level setting
):
    response = await rt.call(
        my_agent,
        "Hello!",
    )

# Final effective configuration:
# - timeout: 300.0 (from session constructor)
# - end_on_error: True (from session constructor)
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
        end_on_error=False,
        save_state=True
    )
else:
    rt.set_config(
        timeout=60.0,
        end_on_error=True,
        save_state=False
    )
```

### Debugging Configuration

```python
import railtracks as rt

# Enhanced debugging setup (use rt.enable_logging(level="DEBUG") at startup for logs)
rt.set_config(
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
## Data directory (`.railtracks`)

When `save_state` is enabled, railtracks resolves the `.railtracks` data directory using the following priority order:

1. **`RAILTRACKS_HOME` environment variable** — set this to the **parent directory** where `.railtracks` should live. Useful for CI environments or shared storage locations.
   ```bash
   export RAILTRACKS_HOME=/path/to/project-root   # .railtracks is created inside here
   ```
2. **Upward directory traversal** — walks up from the current working directory until it finds an existing `.railtracks` folder. This means running scripts from any subdirectory of your project will always resolve to the same directory, as long as you have run `railtracks init` from the project root once.
3. **Fallback to `cwd()`** — if no `.railtracks` directory is found in any parent, one is created in the current working directory. A warning is emitted to prompt you to run `railtracks init` from the intended project root.

The same resolution logic applies to sessions, evaluations, and the visualizer, so all data always lands in one consistent location.

## Important Notes

- `rt.set_config()` must be called **before** any agent execution
- Session constructor parameters always take highest precedence
- Configuration is global and affects all subsequent agent calls
- Default values are used for any unspecified parameters