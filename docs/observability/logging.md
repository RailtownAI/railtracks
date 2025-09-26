# Logging

Railtracks provides built-in logging to help track the execution of your flows. Logs are automatically generated and can be viewed in the terminal or saved to a file.

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

### Logging Levels

Railtracks supports four logging levels:

1. `VERBOSE`: Includes all logs, including `DEBUG`.
2. `REGULAR`: *(Default)* Includes `INFO` and above. Ideal for local development.
3. `QUIET`: Includes `WARNING` and above. Recommended for production.
4. `NONE`: Disables all logging.

```python
--8<-- "docs/scripts/_logging.py:logging_setup"
```

---

### Logging Handlers

#### Console Handler

By default, logs are printed to `stdout` and `stderr`.

#### File Handler

To save logs to a file, pass a `log_file` parameter to the config:

    ```python
    --8<-- "docs/scripts/_logging.py:logging_to_file"
    ```

rt.set_config(log_file="my_logs.log")
```

#### Custom Handlers

    ```python
    --8<-- "docs/scripts/_logging.py:logging_custom_handler"
    ```

---

## Example Usage

You can configure logging globally or per-run.

### Global Configuration

    ```python
    --8<-- "docs/scripts/_logging.py:logging_global"
    ```

rt.set_config(
    logging_setting="VERBOSE",
    log_file="my_logs.log"
)
```

Applies to all flows.

    ```python
    --8<-- "docs/scripts/_logging.py:logging_scoped"

```python
import railtracks as rt

with rt.Session(    
    logging_setting="VERBOSE",
    log_file="my_logs.log"
) as runner:
    # Your code here
    pass
```

Applies only within the context of the `Runner`.

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
