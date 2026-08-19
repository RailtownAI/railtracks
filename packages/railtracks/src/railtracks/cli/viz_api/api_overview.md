# viz_api overview

This is the v2 visualizer API. It reads the event stream stored as JSONL under
`~/.railtracks/data/new-ones/` via DuckDB and serves it to the SPA at
`@railtownai/railtracks-visualizer`. The v1 endpoints live in `viz_server.py`
on the bare `/api/` paths and are frozen — the released visualizer build calls
them and cannot be changed. Everything under this package sits on `/api/v2`
and is free to move.

## Layout

```
viz_api/
├── __init__.py         # exports `router`
├── models.py           # Pydantic response models (the wire contract)
├── row_mapping.py      # dict → Pydantic model helpers
├── routes/             # FastAPI endpoints, one file per resource
│   ├── __init__.py     # top-level router; includes each sub-router under /api/v2
│   ├── _common.py      # shared deps, path pattern, QueryFailureRoute
│   ├── sessions.py     # /sessions, /sessions/{id}, /sessions/{id}/nodes/{nid}, /sessions/{id}/graph
│   ├── llm_traces.py   # /llm-traces
│   ├── events.py       # /events
│   └── middleware.py   # /middleware
└── queries/            # DuckDB SQL, one file per resource
    ├── __init__.py     # re-exports the public callables
    ├── _common.py      # shared CTEs, filter builders, `_rows`, `_parse_json`
    ├── _connection.py  # `EventQuery` singleton + atexit cleanup
    ├── sessions.py     # session summary + stats + filter options
    ├── nodes.py        # per-node rows, LLM totals, tool I/O, agent LLM details
    ├── llm_traces.py   # LLM round-trip listing
    ├── events.py       # raw event log
    ├── middleware.py   # middleware roll-ups
    └── guardrails.py   # per-node guardrail decisions
```

Three concerns are kept apart: the wire contract (`models.py`), the SQL layer
(`queries/`), and the transport layer (`routes/` + `row_mapping.py`). Each is
one directory deep so the boundary is enforced by imports rather than by
convention.

## The query package

Every resource module shares two invariants:

1. **One `WHERE` per resource.** The listing, the count and the stats all read
   the same filter-clause builder (`_session_filters`, `_llm_trace_filters`,
   `_event_filters`, `_middleware_filters`). A tile that describes a different
   set than the table underneath it would be worse than no tile at all, and
   this is where that guarantee comes from.

2. **One shared row CTE.** Where the resource is derived from more than just
   the base namespace view (LLM traces union response + failure; events pull
   in a hop through `llm.*` for middleware attribution; middleware carries
   `raised_here` derivation), that CTE lives in one place and every endpoint
   builds on it.

`_common.py` holds the five CTEs shared across resources
(`_SESSION_JOIN_CTE`, `_NODE_JOIN_CTE`, `_NODE_SPAN_CTE`,
`_MIDDLEWARE_NAME_CTE`, `_LLM_CREATION_JOIN_CTE`). Each is a self-contained
fragment without punctuation — composers add commas at the join sites
(`",".join([...])` or `+ ","`). An earlier version embedded a trailing comma
in each CTE and two callers had to strip it back off with `.rstrip(",")`; the
current shape has one convention that works from either direction.

### Connection lifecycle

`_connection.py` holds a `_ConnectionRegistry` singleton that owns the shared
`EventQuery`. `get_query(events_dir)` opens it on first use and calls
`refresh()` only when the newest `*.jsonl` mtime has moved. A `threading.Lock`
serialises open / refresh / close — defensive for the current
single-event-loop-thread FastAPI setup, and useful if anything ever calls
this from a worker thread. `close_query` is registered via `atexit` so the
connection releases on process exit.

### Enum-derived SQL literals

Where the SQL needs a literal string that matches an enum value (the
`LLMTraceStatus.ERROR` branch of the `llm_calls` status CASE, the seven
`MiddlewareKind.*` values in the kind ladder, the four `MiddlewareOutcome.*`
values in the per-session outcome CASE, and the two `MiddlewareBand.*`
values), the literal is derived from the enum at module import time. So a
rename in `models.py` propagates without a second edit — and there's a single
source of truth for what the SQL and the Pydantic model both agree on.

The middleware-kind CASE is generated from a `_MIDDLEWARE_KIND_LADDER` list
of `(predicate, kind)` tuples for the same reason.

## The route package

Each sub-router has the resource prefix (`/sessions`, `/llm-traces`,
`/events`, `/middleware`) and is included by the top-level router under
`/api/v2`. Session-detail routes are grouped with the session listing in
`sessions.py` because they're all session-scoped.

Two FastAPI dependencies handle the shared preamble:

- **`get_query_or_none`** — list, stats and filter endpoints. Returns `None`
  when the events directory does not exist; the endpoint then returns an
  empty payload of the appropriate shape. This is "nothing recorded yet",
  not an error.
- **`get_query_or_404`** — detail endpoints. Raises `HTTPException(404)` when
  the events directory is missing, because "no events home" is not a valid
  state to answer a detail query from.

### `QueryFailureRoute`

Every sub-router uses a custom `APIRoute` class that wraps each handler with
a shared try/except. Any unhandled exception (except `HTTPException`) is
logged with the request path and re-raised as `HTTPException(500, "failed to
query events")`. That way one query bug doesn't leak the traceback into a
JSON response body, and a failing endpoint reads the same way from the
client's side regardless of which route it's in.

### The `{session_id}` pattern

Session ids are `str(uuid.uuid4())`, so the path parameter carries a
UUID-shape regex. Two reasons:

1. **Route ordering ceases to matter.** FastAPI matches routes in
   registration order, and without the pattern the literals `/sessions/stats`
   and `/sessions/filters` would be shadowed by `/sessions/{session_id}` if
   someone reordered the decorators.
2. **Cheap early validation.** A garbage session id returns `422 Unprocessable
   Entity` at the parameter boundary instead of `404 Session not found` after
   a DuckDB query fires.

Pydantic-core's regex engine has no lookaround, so this is a positive shape
match rather than a negative-lookahead exclusion.

## The event grain

`/api/events` reads the raw `events` view — the envelope plus the untyped
payload. This is deliberately a different grain from `/api/llm-traces`:

- **Trace grain** — one row per LLM round trip. That's a projection that
  unions `llm.response` with `llm.failure` and joins three other event types
  onto it. One round trip is two or more events in the raw stream.
- **Event grain** — one row per event. Reads the raw envelope so it can show
  a namespace the registry doesn't declare. The time column is the
  envelope's `stamp`, not the payload's `timestamp`, because `stamp` is
  present on every event unconditionally.

Neither endpoint is the other under a filter; they answer different
questions.

## Adding an endpoint

Rough recipe:

1. Add / update the Pydantic model in `models.py`.
2. If the endpoint needs new SQL, add a function in the appropriate
   `queries/<resource>.py`. If it aggregates or joins in a way that another
   endpoint already does, share the CTE — don't rewrite it.
3. Re-export the callable from `queries/__init__.py`.
4. If the row shape needs a mapper, add it to `row_mapping.py`.
5. Add the route to the matching `routes/<resource>.py`. Use the
   `get_query_or_none` / `get_query_or_404` dep for the events-dir check.
6. For a session-scoped path parameter, annotate with
   `PathParam(..., pattern=_SESSION_ID_PATTERN)`.

## What's not here

- **No tests.** The event-stream shape is stable enough that a snapshot suite
  over a canned events dir would be worth building; nothing exists yet.
- **No async DuckDB.** `con.execute` is synchronous and blocks the event
  loop. Fine for the current visualizer workload; the bottleneck is DuckDB's
  own query time, not the Python side. If concurrent traffic ever grows,
  `asyncio.to_thread(...)` is the wrap.
- **No structured logging.** The `print_status` calls follow the rest of the
  CLI's convention. If we ever want proper log levels, the whole CLI moves
  together.
