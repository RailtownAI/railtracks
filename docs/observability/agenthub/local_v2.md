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
`.railtracks/beta-ui`.

The beta server opens at `http://localhost:3031`. Its API uses `/api/v2/...`
routes, and interactive API documentation is available at
`http://localhost:3031/docs`.

!!! note "Private beta builds"
    If your Railtracks installation does not provide a beta download URL, set
    `RAILTRACKS_BETA_UI_URL` to the beta UI zip URL before running
    `railtracks update --beta` or the first `railtracks viz --beta` launch.

    You can instead place a built UI directly in `.railtracks/beta-ui` and
    start it without downloading a build.

## Record event-stream data

Configure the JSONL writer before the first agent run in your process:

```python title="Configure local event storage"
from railtracks.observability import JsonlWriter, configure_writers

configure_writers([JsonlWriter()])
```

`JsonlWriter()` and the beta visualizer use the same event directory:
`.railtracks/data/events` under the resolved Railtracks project root.

!!! warning "Configure writers before running an agent"
    `configure_writers(...)` must run before observability starts. Put it in
    your application startup code, before the first flow or agent invocation.

### Use another event directory

Set `RAILTRACKS_EVENTS_DIR` in both the process recording events and the
visualizer process. Relative paths are resolved from the current working
directory.

```bash title="Record and view another event store"
export RAILTRACKS_EVENTS_DIR=./saved-events
python my_agent.py
railtracks viz --beta
```

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
