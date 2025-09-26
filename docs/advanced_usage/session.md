# Session Management

Sessions in Railtracks manage the execution environment for your flows. The recommended approach is using the `@rt.session` decorator for clean, automatic session management.

## The `@rt.session` Decorator

The decorator automatically wraps your __top level__ async functions with a Railtracks session:

```python
--8<-- "docs/scripts/session.py:empty_session_dec"
```

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

??? info "**Session** Context Manager"

    ## When to Use Context Managers

    For more complex scenarios or when you need fine-grained control, use the context manager approach:

    ```python
    --8<-- "docs/scripts/session.py:configured_session_cm"
    ```

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