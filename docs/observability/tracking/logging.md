# Logging

Railtracks emits log records for execution (node creation, completion, failures) but **does not configure logging by default**. To see logs in the terminal or a file, call `enable_logging()` from your application entry point (e.g. `main`, CLI, or server startup). This keeps the library from overriding your—or your host environment’s—logging setup.

!!! note "Session/Flow logging parameters removed"
    Per-session and global-config logging options (`logging_setting`, `log_file` on `Session`, `Flow`, and `set_config()`) were removed. Use `enable_logging(level=..., log_file=...)` at startup (or `RT_LOG_LEVEL` / `RT_LOG_FILE` environment variables) as the single way to configure logging.

??? example "Example Logs"
    ```
    [+  3.525s] ▶ Github Flow  entry: Github Agent
    [+  3.526s]   ▶ Github Agent
    [+  8.040s]     ◆ claude-sonnet-4-6 812→64 tokens · $0.0034 · 4.51s
    [+  8.041s]     ▶ create_issue
    [+  8.685s]     ✓ create_issue 0.644s
    [+ 14.333s]     ◆ claude-sonnet-4-6 1004→71 tokens · $0.0041 · 5.64s
    [+ 14.334s]     ▶ assign_copilot_to_issue
    [+ 14.760s]     ✓ assign_copilot_to_issue 0.426s
    [+ 23.400s]     ◆ claude-sonnet-4-6 1190→112 tokens · $0.0052 · 8.63s
    [+ 23.401s]   ✓ Github Agent 19.875s
    [+ 23.402s] ✓ Github Flow in 19.877s
    ```

---

!!! Critical
    Every log sent by Railtracks will contain a parameter in `extras` for `session_id` which will be uuid tied to the session the error was thrown in.

## Run View

With logging enabled, each run prints as an indented tree built from the run's events: the run itself, every node it calls nested under its caller, and each LLM call with its model, tokens, cost, and latency. The logging level decides how much it shows:

| Level | Run view shows |
|-------|----------------|
| `DEBUG` | Everything below, plus node arguments and responses, guardrail and verifier decisions, and context reads and writes |
| `INFO` | Each node starting and finishing, and each LLM call |
| `WARNING` | The run starting and finishing |
| `ERROR` / `CRITICAL` | Failures only |
| `NONE` | Nothing |

Failures always print, marked `(fatal)` when they stop the run. Each run uses the level of the thread it started in, so calling `enable_logging(level=...)` in a worker thread changes what that thread's runs print.

The run view replaces the console lines for node creation and completion (`<PARENT> CREATED <CHILD>`, `<NODE> DONE`). Those records are still emitted, marked with `rt_lifecycle` in `extras`, and still reach your file handler and any handler you attach yourself. Failure records, with their tracebacks, print as before.

## Configuring Logging

### Enabling logging

Call `enable_logging()` once at application startup. The library never calls it automatically.

```python
--8<-- "docs/scripts/_logging.py:logging_enable"
```

You can set the level and an optional log file path. If you omit them, Railtracks reads `RT_LOG_LEVEL` and `RT_LOG_FILE` from the environment (see below).

### Console logger name

Loggers use dotted names (often from `__name__`), e.g. `RT.railtracks._session`. The **terminal** line can show either a short label or the full name, controlled by `name_style` on `enable_logging()`:

| `name_style` | Console column | Typical use |
|--------------|----------------|-------------|
| `short` (default) | `RT.` plus a short label from the **last** segment: non-letters at the start of that segment are stripped, then it is capitalized (e.g. `…._session` → `RT.Session`, `….state.state` → `RT.State`) | Less cluttered output while keeping a hint of origin |
| `full` | The full logger name (e.g. `RT.railtracks.state.state`) | Debugging when you need the exact module path in every line |

```python
--8<-- "docs/scripts/_logging.py:logging_name_style"
```

File output from `log_file` / `RT_LOG_FILE` still records the **full** dotted `name` on each record; only the console formatter applies `name_style`.

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
    The creation and completion records below reach the file handler and your own handlers; the console shows them through the run view instead.

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