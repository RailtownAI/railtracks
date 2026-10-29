# Logging

Railtracks emits log records for execution ([node](https://docs.railtracks.org/documentation/agent_design/overview/#node) creation, completion, failures) but **does not configure logging by default**. To see logs in the terminal or a file, call `enable_logging()` from your application entry point (e.g. `main`, CLI, or server startup). This keeps the library from overriding your—or your host environment’s—logging setup.

Session/Flow logging parameters removed

Per-session and global-config logging options (`logging_setting`, `log_file` on `Session`, `Flow`, and `set_config()`) were removed. Use `enable_logging(level=..., log_file=...)` at startup (or `RT_LOG_LEVEL` / `RT_LOG_FILE` environment variables) as the single way to configure logging.

Example Logs

```text
[+  3.525s] ▶ Github Flow  entry: Github Agent
[+  3.526s]   ↳ Github Agent
[+  8.040s]     ◆ claude-sonnet-4-6 812→64 tokens · $0.0034 · 4.51s
[+  8.041s]     ↳ create_issue
[+  8.685s]     ✓ create_issue 0.644s
[+ 14.333s]     ◆ claude-sonnet-4-6 1004→71 tokens · $0.0041 · 5.64s
[+ 14.334s]     ↳ assign_copilot_to_issue
[+ 14.760s]     ✓ assign_copilot_to_issue 0.426s
[+ 23.400s]     ◆ claude-sonnet-4-6 1190→112 tokens · $0.0052 · 8.63s
[+ 23.401s]   ✓ Github Agent 19.875s
[+ 23.402s] ✓ Github Flow in 19.877s
```

______________________________________________________________________

Critical

Every log Railtracks sends about a run (node, LLM, and session records) will contain a parameter in `extras` for `session_id` which will be uuid tied to the session the error was thrown in. The observability pipeline's own warnings (`RT.railtracks.observability.*`) don't carry it, since that pipeline logs independently of the run's context.

## Run View

With logging enabled, each run prints as an indented tree built from the run's events: the run itself, every node it calls nested under its caller, and each LLM call with its model, tokens, cost, and latency. The logging level decides how much it shows:

| Level      | Run view shows                                                                                                                        |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `DEBUG`    | Everything below, plus node arguments and responses, the run's result, guardrail and verifier decisions, and context reads and writes |
| `INFO`     | Each node starting and finishing, and each LLM call                                                                                   |
| `WARNING`  | The run starting and finishing                                                                                                        |
| `ERROR`    | Failures only                                                                                                                         |
| `CRITICAL` | Only failures that stop the run                                                                                                       |
| `NONE`     | Nothing                                                                                                                               |

Only `DEBUG` prints node arguments and responses, the run's result, and guardrail reasons. `INFO` and above show names, timings, models, token counts, and costs, so turning logging on doesn't put your users' conversations in your logs. Failure lines print at every level that shows failures and include the exception's message, which can quote user input; provider errors often quote the prompt.

When a node calls several others at once (for example, an agent calling two sub-agents in one turn), their lines interleave, so each line inside those branches starts with the branch's name, as in `Word Analyst › ↳ count_letters`.

In a Jupyter notebook the run view prints into the cell's output as one block, and frames from notebook code show as `<cell>`.

Failures print at `DEBUG` through `ERROR`, marked `(fatal)` when they stop the run, and `CRITICAL` prints only the fatal ones. The lines of your code the exception came through are indented under each failure (railtracks and standard-library frames are left out; `DEBUG` shows them all). A node that its middleware retries shows a `↻ <NODE> retrying after <ERROR>` line, and its final outcome is what the `✓` or `✗` line reports. Each run uses the level of the thread it started in, so calling `enable_logging(level=...)` in a worker thread changes what that thread's runs print.

For the runs it shows, the run view replaces the console lines for node creation, completion, and failure (`<PARENT> CREATED <CHILD>`, `<NODE> DONE`, `<NODE> FAILED`); a node still running after its run has ended prints them as before. Those records are still emitted on the `RT.lifecycle` logger and still reach your file handler and any handler you attach yourself, failures with their full traceback; configure that logger like any other, for example `logging.getLogger("RT.lifecycle").setLevel(logging.WARNING)` to keep only failures.

## Configuring Logging

### Enabling logging

Call `enable_logging()` once at application startup. The library never calls it automatically.

```python
# Call once at application startup (main, CLI, or server entry point).
rt.enable_logging(level="INFO")
```

You can set the level and an optional log file path. If you omit them, Railtracks reads `RT_LOG_LEVEL` and `RT_LOG_FILE` from the environment (see below).

If the `RT` logger already has a handler when you call `enable_logging()`, such as one you attached yourself or one from an earlier `enable_logging()` call, Railtracks leaves that setup alone: it sets the level but adds neither its console (so no [run view](#run-view)) nor the log file. Your handler still receives every record, node creation, completion, and failure included. To get the run view alongside your own handler, call `enable_logging()` first and attach your handler after.

### Console logger name

Loggers use dotted names (often from `__name__`), e.g. `RT.railtracks._session`. The **terminal** line can show either a short label or the full name, controlled by `name_style` on `enable_logging()`:

| `name_style`      | Console column                                                                                                                                                                                     | Typical use                                                 |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| `short` (default) | `RT.` plus a short label from the **last** segment: non-letters at the start of that segment are stripped, then it is capitalized (e.g. `…._session` → `RT.Session`, `….state.state` → `RT.State`) | Less cluttered output while keeping a hint of origin        |
| `full`            | The full logger name (e.g. `RT.railtracks.state.state`)                                                                                                                                            | Debugging when you need the exact module path in every line |

```python
# Console column for the logger name (default is short).
rt.enable_logging(level="INFO")  # name_style="short" (default)
rt.enable_logging(level="INFO", name_style="full")  # full dotted name, e.g. RT.railtracks.foo.bar
```

File output from `log_file` / `RT_LOG_FILE` still records the **full** dotted `name` on each record; only the console applies `name_style`. The console shows the name on `DEBUG`, `WARNING`, `ERROR`, and `CRITICAL` lines; `INFO` lines print as plain notes.

### Logging Levels

Railtracks supports six logging levels aligned with the standard Python logging framework:

1. `DEBUG`: Includes all logs. Ideal for local debugging.
1. `INFO`: Includes `INFO` and above. Good default for development.
1. `WARNING`: Includes `WARNING` and above. Recommended for production.
1. `ERROR`: Includes recoverable issues that prevented part of the system from functioning correctly.
1. `CRITICAL`: Includes severe failures that may cause shutdown.
1. `NONE`: Disables all logging.

```python
# Examples: set level when enabling logging.
rt.enable_logging(level="DEBUG")
rt.enable_logging(level="INFO")
rt.enable_logging(level="CRITICAL")
rt.enable_logging(level="NONE")
```

______________________________________________________________________

### Logging Handlers

Console Handler

Once you call `enable_logging()`, a console handler is added and logs are printed to the terminal, along with the [run view](#run-view). The run view only prints to the console: it isn't written to `log_file` or passed to other handlers, which get the log records instead, node creation, completion, and failure included.

On Windows, when output is redirected to a file or pipe (including most CI runners), set `PYTHONUTF8=1` so the run view's symbols (`▶`, `✓`, `✗`) don't print as escapes such as `\u25b6`. An interactive terminal needs nothing.

File Handler

Pass `log_file` to `enable_logging()` to also write logs to a file:

```python
rt.enable_logging(level="INFO", log_file="my_logs.log")
```

The file is appended to and never rotated or capped. To rotate it, attach a [`RotatingFileHandler`](https://docs.python.org/3/library/logging.handlers.html#rotatingfilehandler) to `RT` yourself instead of passing `log_file`, after calling `enable_logging()` so the console stays on (see [Enabling logging](#enabling-logging)):

```python
import logging
from logging.handlers import RotatingFileHandler

rt.enable_logging(level="INFO")
# up to 5 files of 10 MB each
rotating = RotatingFileHandler(
    "my_logs.log", maxBytes=10_000_000, backupCount=5, encoding="utf-8"
)
rotating.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
)
logging.getLogger("RT").addHandler(rotating)
```

File Handler logging level

The file handler records `INFO` and above, even when you pass `level="DEBUG"`; the level only changes the console. If you'd like us to support customizing this parameter, please open an issue at [railtracks/issues](https://github.com/RailtownAI/railtracks/issues)

Custom Handlers

Railtracks uses the standard [Python `logging`](https://docs.python.org/3/library/logging.html) module. All framework loggers live under the **`RT`** name (e.g. `RT.railtracks.state.state`). To see only Railtracks logs and not third-party libraries (e.g. litellm), attach your handler to `logging.getLogger("RT")`:

```python
import logging


class CustomHandler(logging.Handler):
    def emit(self, record):
        # Custom logging logic
        pass


# Attach to "RT" to see only Railtracks logs (not e.g. litellm).
logger = logging.getLogger("RT")
logger.addHandler(CustomHandler())
```

______________________________________________________________________

## Example usage

Enable logging at startup

```python
rt.enable_logging(level="DEBUG", log_file="my_logs.log")
```

Environment variables

You can set `RT_LOG_LEVEL` and `RT_LOG_FILE` in your environment (or `.env`). They are used as defaults when you call `enable_logging()` without arguments.

```python
# Set in shell or .env; used as defaults when you call enable_logging() without arguments.
# RT_LOG_LEVEL=DEBUG
# RT_LOG_FILE=my_logs.log
```

______________________________________________________________________

## Forwarding Logs to External Services

You can forward logs to services like [Loggly](https://www.loggly.com/), [Sentry](https://sentry.io/), or [Conductr](https://conductr.ai) by attaching custom handlers. Refer to each provider's documentation for integration details.

```python
import railtownai

RAILTOWN_API_KEY = "YOUR_RAILTOWN_API_KEY"
railtownai.init(RAILTOWN_API_KEY)
```

```python
import logging
from loggly.handlers import HTTPSHandler

LOGGLY_TOKEN = "YOUR_LOGGLY_TOKEN"
https_handler = HTTPSHandler(
    url=f"https://logs-01.loggly.com/inputs/{LOGGLY_TOKEN}/tag/python"
)
logger = logging.getLogger("RT")
logger.addHandler(https_handler)
```

```python
import sentry_sdk

sentry_sdk.init(
    dsn="https://examplePublicKey@o0.ingest.sentry.io/0",
    send_default_pii=True,  # Collects additional metadata
)
```

______________________________________________________________________

## Log Message Examples

Each example shows a record as `<LOGGER> : <LEVEL> - <MESSAGE>`, with the logger name as `name_style="short"` prints it. The console uses that layout for `DEBUG`, `WARNING`, `ERROR`, and `CRITICAL` records and prints `INFO` records as dim notes (`· <MESSAGE>`). Records about nodes starting, finishing, and failing come from the `RT.lifecycle` logger and reach the file handler and your own handlers, failures with their full traceback; the console shows them through the run view instead, while that run is in it.

DEBUG Messages

| Type            | Example                                                    |
| --------------- | ---------------------------------------------------------- |
| Session Created | `RT.Session : DEBUG - Session <SESSION_ID> is initialized` |

INFO Messages

| Type            | Example                                                                                          |
| --------------- | ------------------------------------------------------------------------------------------------ |
| Initial Request | `RT.Lifecycle: INFO - START CREATED <NODE_NAME>`                                                 |
| Invoking Nodes  | `RT.Lifecycle: INFO - <PARENT_NODE_NAME> CREATED <CHILD_NODE_NAME>`                              |
| Node Completed  | `RT.Lifecycle: INFO - <NODE_NAME> DONE`                                                          |
| Run Data Saved  | `RT.Session : INFO - Saving run data to .railtracks/data/sessions/<FLOW_NAME>_<SESSION_ID>.json` |

WARNING Messages

| Type              | Example                                                                                                                                 |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| No System Message | `RT.Validation: WARNING - No SystemMessage was provided. This is not recommended. Please provide the first message as a SystemMessage.` |

ERROR and CRITICAL Messages

| Type              | Example                                       |
| ----------------- | --------------------------------------------- |
| Node Failed       | `RT.Lifecycle: ERROR - <NODE_NAME> FAILED`    |
| Node Failed Fatal | `RT.Lifecycle: CRITICAL - <NODE_NAME> FAILED` |
