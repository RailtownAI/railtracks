# Logging

Railtracks emits log records for execution (node creation, completion, failures) but **does not configure logging by default**. To see logs in the terminal or a file, call `enable_logging()` from your application entry point (e.g. `main`, CLI, or server startup). This keeps the library from overriding your—or your host environment’s—logging setup.

??? example "Example Logs"
    ```
    [+3.525  s] RT          : INFO     - START CREATED Github Agent
    [+8.041  s] RT          : INFO     - Github Agent CREATED create_issue
    [+8.685  s] RT          : INFO     - create_issue DONE
    [+14.333 s] RT          : INFO     - Github Agent CREATED assign_copilot_to_issue
    [+14.760 s] RT          : INFO     - assign_copilot_to_issue DONE
    [+17.540 s] RT          : INFO     - Github Agent CREATED assign_copilot_to_issue
    [+18.961 s] RT          : INFO     - assign_copilot_to_issue DONE
    [+23.401 s] RT          : INFO     - Github Agent DONE
    ```

---

!!! Critical
    Every log sent by Railtracks will contain a parameter in `extras` for `session_id` which will be uuid tied to the session the error was thrown in.

## Configuring Logging

### Enabling logging

Call `enable_logging()` once at application startup. The library never calls it automatically.

```python
--8<-- "docs/scripts/_logging.py:logging_enable"
```

You can set the level and an optional log file path. If you omit them, Railtracks reads `RT_LOG_LEVEL` and `RT_LOG_FILE` from the environment (see below).

### Logging Levels

Railtracks supports six logging levels aligned with the standard Python logging framework:

1. `DEBUG`: Includes all logs. Ideal for local debugging.
2. `INFO`: Includes `INFO` and above. Good default for development.
3. `WARNING`: Includes `WARNING` and above. Recommended for production.
4. `ERROR`: Includes recoverable issues that prevented part of the system from functioning correctly.
5. `CRITICAL`: Includes severe failures that may cause shutdown.
6. `NONE`: Disables all logging.

```python
--8<-- "docs/scripts/_logging.py:logging_setup"
```

---

### Logging Handlers

!!! tip "Console Handler"

    Once you call `enable_logging()`, a console handler is added and logs are printed to the terminal.

!!! tip "File Handler"

    Pass `log_file` to `enable_logging()` to also write logs to a file:

    ```python
    --8<-- "docs/scripts/_logging.py:logging_to_file"
    ```

!!! warning "File Handler logging level"
    Currently the logs outputted to the File Handler will be at `DEBUG` level for completeness. If you'd like us to support customizing this parameter, please open an issue at [railtracks/issues](https://github.com/RailtownAI/railtracks/issues)

!!! tip "Custom Handlers"

    Railtracks uses the standard [Python `logging`](https://docs.python.org/3/library/logging.html) module. All framework loggers live under the **`RT`** name (e.g. `RT.railtracks.state.state`). To see only Railtracks logs and not third-party libraries (e.g. litellm), attach your handler to `logging.getLogger("RT")`:

    ```python
    --8<-- "docs/scripts/_logging.py:logging_custom_handler"
    ```

---

## Example usage

!!! example "Enable logging at startup"

    ```python
    --8<-- "docs/scripts/_logging.py:logging_global"
    ```

!!! example "Environment variables"

    You can set `RT_LOG_LEVEL` and `RT_LOG_FILE` in your environment (or `.env`). They are used as defaults when you call `enable_logging()` without arguments.

    ```python
    --8<-- "docs/scripts/_logging.py:logging_env_var"
    ```

---

## Forwarding Logs to External Services

You can forward logs to services like [Loggly](https://www.loggly.com/), [Sentry](https://sentry.io/), or [Conductr](https://conductr.ai) by attaching custom handlers. Refer to each provider's documentation for integration details.

=== "Conductr"

    ```python
    --8<-- "docs/scripts/_logging.py:logging_railtown"
    ```

=== "Loggly"

    ```python
    --8<-- "docs/scripts/_logging.py:logging_loggly"
    ```

=== "Sentry"

    ```python
    --8<-- "docs/scripts/_logging.py:logging_sentry"
    ```

---

## Log Message Examples

??? note "DEBUG Messages"
    | Type           | Example |
    |----------------|---------|
    | Runner Created | `RT.Runner   : DEBUG    - Runner <RUNNER_ID> is initialized` |
    | Node Created   | `RT.Publisher: DEBUG    - RequestCreation(current_node_id=<PARENT_NODE_ID>, new_request_id=<REQUEST_ID>, running_mode=async, new_node_type=<NODE_NAME>, args=<INPUT_ARGS>, kwargs=<INPUT_KWARGS>)` |
    | Node Completed | `RT.Publisher: DEBUG    - <NODE_NAME> DONE with result <RESULT>` |

??? note "INFO Messages"
    | Type             | Example |
    |------------------|---------|
    | Initial Request  | `RT          : INFO     - START CREATED <NODE_NAME>` |
    | Invoking Nodes   | `RT          : INFO     - <PARENT_NODE_NAME> CREATED <CHILD_NODE_NAME>` |
    | Node Completed   | `RT          : INFO     - <NODE_NAME> DONE` |
    | Run Data Saved   | `RT.Runner   : INFO     - Saving execution info to .railtracks\<RUNNER_ID>.json` |

??? note "WARNING Messages"
    | Type              | Example |
    |-------------------|---------|
    | Overwriting File  | `RT.Runner   : WARNING  - File .railtracks\<RUNNER_ID>.json already exists, overwriting...` |

??? note "ERROR Messages"
    | Type        | Example |
    |-------------|---------|
    | Node Failed | `RT          : ERROR    - <NODE_NAME> FAILED` |
