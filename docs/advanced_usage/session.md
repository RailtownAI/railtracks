# Session Management

Sessions in Railtracks manage the execution environment for your flows. There are three approaches, listed here in order of recommendation:

## 1. Flow (Recommended)

The **`Flow`** class provides the cleanest abstraction for packaging and executing workflows:

```python
import railtracks as rt

@rt.function_node
async def my_workflow(user_input: str):
    result = await rt.call(MyAgent, user_input)
    return result

# Create and run a Flow
flow = rt.Flow(
    "My Workflow", 
    entry_point=my_workflow,
    timeout=60,
    context={"api_key": "secret"},
    logging_setting="INFO"
)

result = flow.invoke("Hello!")  # Synchronous
# or
result = await flow.ainvoke("Hello!")  # Asynchronous
```

**Benefits:**
- Clean, reusable workflow abstraction
- Automatic session management
- Both sync and async execution methods
- Named workflows for better observability

## 2. The `@rt.session` Decorator

The decorator automatically wraps your __top level__ async functions with a Railtracks session:

```python
--8<-- "docs/scripts/session.py:empty_session_dec"
```

**Benefits:**
- Pythonic decorator syntax
- Returns both result and session object
- Simpler than Flow for one-off workflows

### Configuring Your Session

The decorator supports all session configuration options:

```python
--8<-- "docs/scripts/session.py:configured_session_dec"
```

### Multiple Workflows

Each decorated function gets its own isolated session:

```python
--8<-- "docs/scripts/session.py:multiple_sessions_dec"
```

!!! warning "Important Notes"

    - **Async Only**: The **`@rt.session`** decorator only works with async functions. Using it on sync functions raises a **`TypeError`**
    - **Automatic Cleanup**: Sessions automatically clean up resources when functions complete
    - **Unique Identifiers**: Each session gets a unique identifier for tracking and debugging. If you do use the same identifier in different flows, their unique saved states will overwrite with the warning:
        **`RT.Session  : WARNING  - File .railtracks/my-unique-run.json already exists, overwriting...`**.

## 3. Session Context Manager (Advanced)

For complex scenarios requiring fine-grained control, use the context manager approach:

```python
--8<-- "docs/scripts/session.py:configured_session_cm"
```

**Use this when you need:**
- Fine-grained control over session lifecycle
- Multiple workflows within the same session context
- Dynamic session configuration based on runtime conditions

!!! note "Choosing the Right Approach"
    - **Flow**: Best for reusable, named workflows that may be invoked multiple times
    - **@rt.session**: Best for simple, one-off async workflows
    - **Context Manager**: Only when you need fine-grained control over session lifecycle

??? info "More Examples"

    !!! example "Error Handling"
        ```python
        --8<-- "docs/scripts/session.py:error_handling"
        ```

    !!! example "API Workflows"
        ```python
        --8<-- "docs/scripts/session.py:api_example"
        ```
    !!! example "Tracked Execution"
        ```python
        --8<-- "docs/scripts/session.py:tracked"
        ```