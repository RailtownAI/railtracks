# Local Visualization (Beta)

The beta visualizer reads Railtracks' JSONL event stream and provides the
latest session table, filtering, sorting, and pagination experience. It is
installed separately from the [stable visualizer](local.md), so both versions
can be used in the same project.

!!! warning "Beta software"
    The beta UI and `/api/v2` contract are under active development. Response
    fields, filters, and other behavior can change between releases without
    notice.

## Install and start

Install the optional visualization dependencies:

```bash title="Install the CLI visualization tools"
pip install 'railtracks[visual]'
```

Initialize Railtracks from your project root, install the beta UI, and start
the server:

```bash title="Initialize and start the beta visualizer"
railtracks init
railtracks update --beta
railtracks viz --beta
```

`railtracks init` creates the `.railtracks` directory and installs the stable
UI. `railtracks update --beta` installs the beta build alongside it in
`.railtracks/beta-ui`. If the beta UI is missing, `railtracks viz --beta`
downloads it automatically before starting the server.

The beta server opens at `http://localhost:3031`. Its API uses `/api/v2/...`
routes, and interactive API documentation is available at
`http://localhost:3031/docs`.

## Record event-stream data

Events are recorded automatically to `.railtracks/data/events` with no setup required. The beta visualizer reads from the
same directory.

### Customize event writers

To use your own writer set (or add more alongside the default), call
`configure_writers(...)` before the first flow invocation in your process:

```python title="Configure local event storage"
--8<-- "docs/scripts/observability/events.py:v2-viz"
```

!!! warning "`configure_writers`"
    `configure_writers` overwrites the default behaviour so if you'd like
    to still have the local events files, you need the pass the `JsonlWriter()` as well as
    any new or custom writers

### Use another event directory

Set `RAILTRACKS_EVENTS_DIR` in both the process recording events and the
visualizer process. Relative paths are resolved from the current working
directory. This redirects the auto-injected writer without any code change.

```bash title="Record and view another event store"
export RAILTRACKS_EVENTS_DIR=./saved-events
python my_agent.py
railtracks viz --beta
```

### Deployed environments with no writable disk

Set `RAILTRACKS_DISABLE_EVENTS=1` on hosts where Railtracks can't (or
shouldn't) write to disk. It skips **both** the auto-registered event
writer and the legacy `save_state` session dump, regardless of what
`save_state=` is set to.

```bash title="Turn off Railtracks-owned disk writes"
export RAILTRACKS_DISABLE_EVENTS=1
```

For hosted observability in these environments, use Conductr.

!!! warning "`save_state` is deprecated"
    `save_state=True` still writes `.railtracks/data/sessions/*.json` for the
    stable (v1) visualizer this release, but passing the argument at all now
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

```bash title="Start beta mode with API diagnostics"
railtracks viz --beta --debug
```

Debug mode writes newline-delimited JSON records to stderr for v2 requests,
DuckDB queries, and event-store connection changes.

!!! warning "Debug logs can contain user input"
    Request records include query parameter values, such as search terms.
    Review or redact debug output before sharing it or sending it to a log
    collector.

## Update the beta UI

Stable and beta builds are updated independently. Refresh only the beta build
with:

```bash title="Update the beta UI"
railtracks update --beta
```
