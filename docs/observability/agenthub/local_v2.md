# Local Visualization (Current)

Conductr Local is the current local visualizer for Railtracks. It reads the JSONL event stream that every run records, and lets
you browse runs, LLM calls, middleware decisions, and raw events, with
filtering, sorting, and pagination on every table. It is installed separately
from the [legacy visualizer](local.md), so both can be used in the same
project.

![The Agent Traces page of the current visualizer](https://railtracksstorage.blob.core.windows.net/railtrackswebsite/images/v2-visualizer/agent-traces-light.png#only-light)
![The Agent Traces page of the current visualizer](https://railtracksstorage.blob.core.windows.net/railtrackswebsite/images/v2-visualizer/agent-traces-dark.png#only-dark)

!!! warning "Still in beta"
    The current visualizer is still in beta, which is why it's started with
    `--beta`. Its UI and `/api/v2` contract are under active development. Response
    fields, filters, and other behavior can change between releases without
    notice.

## Install and start

Install the optional visualization dependencies:

```bash title="Install the CLI visualization tools"
pip install 'railtracks[visual]'
```

Initialize Railtracks from your project root, install the beta UI, and start
the server:

```bash title="Initialize and start the current visualizer"
railtracks init
railtracks update --beta
railtracks viz --beta
```

`railtracks init` creates the `.railtracks` directory and installs the legacy
UI. `railtracks update --beta` installs the beta build alongside it in
`.railtracks/beta-ui`. If the beta UI is missing, `railtracks viz --beta`
downloads it automatically before starting the server.

The server opens at `http://localhost:3031`. Its API uses `/api/v2/...`
routes, and interactive API documentation is available at
`http://localhost:3031/docs`.

The page doesn't update on its own. After a new run, press **Refresh** at the
top right of any page to load it.

## Agent Traces

**Agent Traces** is the home page. Each row is one run of a flow, with its
status, entry point, the middleware it passed through, cost, tokens (input and
output), duration, and start time.

- The tiles at the top summarize every run that matches the current filters.
  Click **Failures** or **Blocked** to show only those runs, and click again to
  clear the filter.
- Narrow the list by date range (24h, 7 days, 30 days, All, or a custom range),
  flow name, entry point, or status.
- Show, hide, and resize columns with **Columns**. Your layout is remembered in
  the browser.

A run is **Completed** or **Failed**, or **Blocked** when a guardrail or verifier
stopped it. Click a middleware icon in a row to open that middleware's
decisions for the run.

## Session details

Click a run to open its session. The tree on the left shows every node the run
called, nested under the node that called it, with each one's latency. Select a
node to see its cost, tokens, inputs, and outputs on the right. For an agent,
that's the full message history it sent to the model.

![A session with the Research Lead agent selected](https://railtracksstorage.blob.core.windows.net/railtrackswebsite/images/v2-visualizer/session-details-light.png#only-light)
![A session with the Research Lead agent selected](https://railtracksstorage.blob.core.windows.net/railtrackswebsite/images/v2-visualizer/session-details-dark.png#only-dark)

When a node made more than one LLM call, a table lists each call's model,
tokens, cost, and latency. Select a call to see exactly what that call sent.

Nodes that raised an exception are marked **Failed**. To read the exception
itself, open the run's events (see [Event Logs](#event-logs)) and select its
`node.failure` event.

![A failed run with the fetch_metrics tool selected](https://railtracksstorage.blob.core.windows.net/railtrackswebsite/images/v2-visualizer/session-failed-light.png#only-light)
![A failed run with the fetch_metrics tool selected](https://railtracksstorage.blob.core.windows.net/railtrackswebsite/images/v2-visualizer/session-failed-dark.png#only-dark)

Buttons at the top of the session:

- **Visualizer** switches to a graph of the run. Click a node to inspect it,
  and use **Session Details** to switch back.
- **Events** opens [Event Logs](#event-logs) filtered to this run.
- The copy button copies the session ID.

![The graph view of a parallel code review run](https://railtracksstorage.blob.core.windows.net/railtrackswebsite/images/v2-visualizer/session-graph-light.png#only-light)
![The graph view of a parallel code review run](https://railtracksstorage.blob.core.windows.net/railtrackswebsite/images/v2-visualizer/session-graph-dark.png#only-dark)

## LLM Traces

**LLM Traces** lists every model call across all runs, with the flow, agent,
model, tokens, cost, and latency. The tiles show the call count, errors, total
tokens and cost, average latency, and the slowest call. Click **Errors** to
show only failed calls. Filter by flow, agent, or model.

![The LLM Traces page](https://railtracksstorage.blob.core.windows.net/railtrackswebsite/images/v2-visualizer/llm-traces-light.png#only-light)
![The LLM Traces page](https://railtracksstorage.blob.core.windows.net/railtrackswebsite/images/v2-visualizer/llm-traces-dark.png#only-dark)

Click a call to see its messages, its output, the provider, and the error if
it failed. **Open in session** jumps to the node that made the call.

![One LLM call opened from LLM Traces](https://railtracksstorage.blob.core.windows.net/railtrackswebsite/images/v2-visualizer/llm-trace-details-light.png#only-light)
![One LLM call opened from LLM Traces](https://railtracksstorage.blob.core.windows.net/railtrackswebsite/images/v2-visualizer/llm-trace-details-dark.png#only-dark)

## Middleware

**Middleware** rolls up every [middleware](../../documentation/agent_design/middleware/overview.md)
across all runs. One row is one middleware: how often it ran, how many
decisions it made, how many calls it blocked or interrupted, and how many
sessions it appeared in.

![The Middleware page with a guardrail and a verifier](https://railtracksstorage.blob.core.windows.net/railtrackswebsite/images/v2-visualizer/middleware-light.png#only-light)
![The Middleware page with a guardrail and a verifier](https://railtracksstorage.blob.core.windows.net/railtrackswebsite/images/v2-visualizer/middleware-dark.png#only-dark)

**Kind** is what the middleware does:

| Kind | Created with |
|---|---|
| Input guard | `@input_guard` |
| Output guard | `@output_guard` |
| Request transform | `@before_llm` |
| Response transform | `@after_llm` |
| Result hook | `@after_node` |
| LLM wrapper | `@wrap_llm` |
| Node wrapper | `@wrap_node` |
| Verifier | `pre_verifier`, `post_verifier` |

**Band** is where it was attached: **Node** for `middleware=` and **LLM** for
`model_middleware=`.

Click **Blocks** to show only middleware that blocked something. The
**Framework** switch also shows the middleware Railtracks adds internally for
observability, which is hidden by default.

Click a row for its full roll-up, including when it was first and last seen and
the reason it gave for its latest decision. **View events** opens its events in
Event Logs.

![A verifier's roll-up with the reason for its latest decision](https://railtracksstorage.blob.core.windows.net/railtrackswebsite/images/v2-visualizer/middleware-details-light.png#only-light)
![A verifier's roll-up with the reason for its latest decision](https://railtracksstorage.blob.core.windows.net/railtrackswebsite/images/v2-visualizer/middleware-details-dark.png#only-dark)

## Event Logs

**Event Logs** is the raw event stream: every event Railtracks recorded, newest
first. Search the payloads, or filter by namespace (such as `node`, `llm`, or
`middleware`), event type, and flow. Click **Failures** to show only events
that reported an exception.

![The Event Logs page](https://railtracksstorage.blob.core.windows.net/railtrackswebsite/images/v2-visualizer/event-logs-light.png#only-light)
![The Event Logs page](https://railtracksstorage.blob.core.windows.net/railtrackswebsite/images/v2-visualizer/event-logs-dark.png#only-dark)

Click an event to see its full payload. For a failure, that includes the
exception's name and message. **Open in session** jumps to the run, with the
event's node selected.

![A node.failure event showing the exception](https://railtracksstorage.blob.core.windows.net/railtrackswebsite/images/v2-visualizer/event-failure-light.png#only-light)
![A node.failure event showing the exception](https://railtracksstorage.blob.core.windows.net/railtrackswebsite/images/v2-visualizer/event-failure-dark.png#only-dark)

Middleware events carry each decision. Here, a `pre_verifier` declined a refund
and recorded why, along with the arguments it was asked to approve:

![A verifier decision event declining a refund](https://railtracksstorage.blob.core.windows.net/railtrackswebsite/images/v2-visualizer/event-details-light.png#only-light)
![A verifier decision event declining a refund](https://railtracksstorage.blob.core.windows.net/railtrackswebsite/images/v2-visualizer/event-details-dark.png#only-dark)

## Evaluations

Evaluations aren't in the current visualizer yet. Its **Evaluations** page is a
placeholder. To browse evaluation results, use the
[legacy visualizer](local.md) as described in
[Evaluation Visualization](../../evaluations/visualization.md).

## Keyboard shortcuts

Press `Shift`+`?` anywhere to list the shortcuts.

| Keys | Action |
|---|---|
| `Shift`+`D` | Switch between light and dark |
| `Shift`+`` ` `` | Show or hide the sidebar |
| `G` then `A` | Agent Traces |
| `G` then `T` | LLM Traces |
| `G` then `M` | Middleware |
| `G` then `L` | Event Logs |
| `G` then `R` | Middleware, guardrails only |

![The keyboard shortcuts dialog](https://railtracksstorage.blob.core.windows.net/railtrackswebsite/images/v2-visualizer/keyboard-shortcuts-light.png#only-light)
![The keyboard shortcuts dialog](https://railtracksstorage.blob.core.windows.net/railtrackswebsite/images/v2-visualizer/keyboard-shortcuts-dark.png#only-dark)

## Share a view

These URLs open a specific view, so you can bookmark them or send them to
someone looking at the same event store:

| URL | Opens |
|---|---|
| `#/agent-traces/<session_id>` | A session |
| `#/agent-traces/<session_id>?nodeId=<node_id>` | A session with one node selected |
| `#/events?session_id=<session_id>` | One run's events |
| `#/middleware?session_id=<session_id>` | The middleware used in one run |

Other filters, sorting, and paging aren't kept in the URL.

## Record event-stream data

Events are recorded automatically to `.railtracks/data/events` with no setup required. The current visualizer reads from the
same directory.

### Customize event writers

To use your own writer set (or add more alongside the default), call
`configure_writers(...)` before the first flow invocation in your process:

```python title="Configure local event storage"
--8<-- "docs/scripts/observability/events.py:v2-viz"
```

!!! warning "`configure_writers`"
    `configure_writers` replaces the auto-registered default, so if you'd like
    to still have the local event files, you need to pass `JsonlWriter()` as
    well as any new or custom writers.

### Use another event directory

Set `RAILTRACKS_EVENTS_DIR` in both the process recording events and the
visualizer process. Relative paths are resolved from the current working
directory. This redirects the auto-injected writer without any code change.

```bash title="Record and view another event store"
export RAILTRACKS_EVENTS_DIR=./saved-events
python my_agent.py
railtracks viz --beta
```

### Choose what context events record

`rt.context` calls are recorded as `context.*` events. Set `RAILTRACKS_CONTEXT_EVENTS` to `0` for no context events, `1` for keys without values, or `2` (the default) for keys and values. Every other event is recorded either way. See [Global Context](../../documentation/advanced/context.md#choosing-whats-recorded) for details.

```bash title="Record context keys but not their values"
export RAILTRACKS_CONTEXT_EVENTS=1
```

### Deployed environments with no writable disk

Set `RAILTRACKS_DISABLE_EVENTS=True` on hosts where Railtracks can't (or
shouldn't) write to disk. It skips **both** the auto-registered event
writer and the legacy `save_state` session dump, regardless of what
`save_state=` is set to.

```bash title="Turn off Railtracks-owned disk writes"
export RAILTRACKS_DISABLE_EVENTS=True
```

For hosted observability in these environments, use Conductr.

!!! warning "`save_state` is deprecated"
    `save_state=True` still writes `.railtracks/data/sessions/*.json` for the
    legacy visualizer this release, but passing the argument at all now
    emits a `DeprecationWarning`. The file dump is being replaced by the
    event stream (`.railtracks/data/events/`). Default: `True` this release,
    flips to `False` next release. Remove the argument to let the framework
    default take over.

!!! tip "Running from multiple directories?"
    Run `railtracks init` once from your project root, at the same level as
    your `.git` directory. Railtracks walks up from the current directory to
    locate that project's `.railtracks` directory.

    For a fixed location, set `RAILTRACKS_HOME` to the parent directory where
    `.railtracks` should live. `RAILTRACKS_HOME` takes priority over directory
    traversal.

## Debug the API

Add `--debug` to emit structured diagnostics:

```bash title="Start with API diagnostics"
railtracks viz --beta --debug
```

Debug mode writes newline-delimited JSON records to stderr for v2 requests,
DuckDB queries, and event-store connection changes.

!!! warning "Debug logs can contain user input"
    Request records include query parameter values, such as search terms.
    Review or redact debug output before sharing it or sending it to a log
    collector.

## Update the UI

The legacy and current builds are updated independently. Refresh only the
current build, in `.railtracks/beta-ui`, with:

```bash title="Update the current visualizer"
railtracks update --beta
```
