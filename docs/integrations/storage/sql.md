# SQL / Relational Databases

`SQLLoader` reads rows from any **SQLAlchemy-compatible relational database** and
returns them as [`Chunk`](../../rag/vector_stores/vector_store_info.md) objects.
Works with PostgreSQL, Supabase, MySQL, SQLite, and more.

## Installation

=== "pip"

    ```bash
    pip install railtracks[sql]
    ```

=== "uv"

    ```bash
    uv add railtracks[sql]
    ```

For PostgreSQL / Supabase you also need a driver:

=== "pip"

    ```bash
    pip install psycopg2-binary   # PostgreSQL (most common)
    ```

=== "uv"

    ```bash
    uv add psycopg2-binary
    ```

## Connecting

Pass a [SQLAlchemy database URL](https://docs.sqlalchemy.org/en/20/core/engines.html#database-urls):

| Database | URL format |
|---|---|
| PostgreSQL | `postgresql+psycopg2://user:pass@host/db` |
| Supabase | `postgresql+psycopg2://postgres:pass@db.<ref>.supabase.co:5432/postgres` |
| MySQL | `mysql+pymysql://user:pass@host/db` |
| SQLite (file) | `sqlite:///path/to/file.db` |
| SQLite (memory) | `sqlite:///:memory:` |

## Basic usage — PostgreSQL

```python
--8<-- "docs/scripts/storage_loaders.py:sql_basic_postgres"
```

## Supabase

```python
--8<-- "docs/scripts/storage_loaders.py:sql_supabase"
```

## Raw SQL query

Pass any `SELECT` statement instead of a table name for filtering, joining, or
transforming data before it reaches the loader:

```python
--8<-- "docs/scripts/storage_loaders.py:sql_raw_query"
```

!!! warning "CTE (`WITH`) queries are not supported directly"
    `table_or_query` is detected as a raw query only when the string starts with
    `SELECT`.  Queries beginning with `WITH` (Common Table Expressions) are
    treated as table names and will cause a database error.

    **Workaround** — wrap your CTE in a subquery:

    ```python
    loader = SQLLoader(
        connection_string,
        table_or_query="""
            SELECT * FROM (
                WITH ranked AS (
                    SELECT id, body, ROW_NUMBER() OVER (ORDER BY created_at DESC) AS rn
                    FROM docs
                )
                SELECT id, body FROM ranked WHERE rn <= 100
            ) AS t
        """,
        content_column="body",
        id_column="id",
    )
    ```

## Load specific rows by ID

```python
--8<-- "docs/scripts/storage_loaders.py:sql_load_keys"
```

!!! note
    `load_keys()` requires `id_column` to be set when constructing the loader.

## Reuse an existing engine

When you already have a configured `sqlalchemy.Engine` (custom pool size, SSL
certificates, read replicas, etc.) pass it directly via the `engine` parameter:

```python
--8<-- "docs/scripts/storage_loaders.py:sql_existing_engine"
```

!!! tip "Engine ownership"
    When you supply your own `engine`, the loader does **not** dispose it on
    `close()`.  You remain responsible for its lifecycle.  When the loader
    creates its own engine (the default), `close()` disposes it for you.

## Engine lifecycle — close and context manager

For long-lived applications or scripts that create many loaders, explicitly
releasing the connection pool avoids resource leaks:

```python
# Explicit close
loader = SQLLoader(connection_string, "documents", "body")
try:
    chunks = loader.load()
finally:
    loader.close()

# Context-manager (preferred)
with SQLLoader(connection_string, "documents", "body") as loader:
    chunks = loader.load()
```

## Async usage

```python
--8<-- "docs/scripts/storage_loaders.py:sql_async"
```

!!! note "Async is thread-backed"
    `aload()` and `aload_keys()` run the synchronous SQLAlchemy driver on a
    thread-pool thread via `asyncio.to_thread()`.  This works correctly but
    occupies a thread for the full duration of the query.  For very
    high-concurrency workloads consider wiring up a true async engine
    (e.g. `asyncpg` with `sqlalchemy.ext.asyncio`) and passing it via the
    `engine` parameter.

## Chunk metadata

Each returned `Chunk` carries:

| Key | Value |
|---|---|
| `source` | The `table_or_query` string used to construct the loader |
| _any `metadata_columns`_ | One key per column listed in `metadata_columns` |

When `metadata_columns` is `None`, all columns except `content_column` and
`id_column` are included automatically.

## Full RAG pipeline example

```python
--8<-- "docs/scripts/storage_loaders.py:pipeline_sql_to_rag"
```

---

## Writing to SQL databases

`SQLWriter` inserts or upserts rows into any SQLAlchemy-compatible database.
The table must already exist.

### Basic write — PostgreSQL

```python
--8<-- "docs/scripts/storage_writers.py:sql_write_basic"
```

### Supabase

```python
--8<-- "docs/scripts/storage_writers.py:sql_write_supabase"
```

### Insert vs upsert modes

```python
--8<-- "docs/scripts/storage_writers.py:sql_write_modes"
```

!!! note "Upsert mechanics"
    In `"upsert"` mode the writer issues a `DELETE` followed by an `INSERT`
    inside a single transaction, which works across all SQLAlchemy-compatible
    databases including SQLite, PostgreSQL, and MySQL.  This is not the same
    as a native `ON CONFLICT DO UPDATE` — it acquires a delete lock for the
    duration of the insert, which may affect concurrent write throughput under
    heavy load.

!!! warning "All-or-nothing batch writes"
    All chunks passed to a single `write()` call are committed inside **one
    transaction**.  If any individual row fails (constraint violation, type
    mismatch, etc.) the **entire batch is rolled back** and no rows are
    written.  The exception from the failing row is re-raised so you can
    inspect it.

    To tolerate partial failures, call `write_key()` per chunk in a loop:

    ```python
    writer = SQLWriter(connection_string, "documents", "body", id_column="id")
    written, failed = [], []
    for chunk in chunks:
        try:
            uri = writer.write_key(chunk.id, chunk.content)
            written.append(uri)
        except Exception as exc:
            failed.append((chunk, exc))
    ```

### Engine lifecycle — close and context manager

```python
# Context-manager (preferred)
with SQLWriter(connection_string, "documents", "body", id_column="id") as writer:
    writer.write(chunks)

# Explicit close
writer = SQLWriter(connection_string, "documents", "body", id_column="id")
try:
    writer.write(chunks)
finally:
    writer.close()
```

### Reuse an existing engine

```python
--8<-- "docs/scripts/storage_writers.py:sql_write_existing_engine"
```

### Async write

```python
--8<-- "docs/scripts/storage_writers.py:sql_write_async"
```

!!! note "Async is thread-backed"
    `awrite()` and `awrite_key()` delegate to `asyncio.to_thread()`, the same
    as the loader.  See the async note in the loader section above.

### Chunk-to-row mapping

| Chunk field | SQL column |
|---|---|
| `chunk.content` | `content_column` (required) |
| `chunk.id` | `id_column` (when set) |
| `chunk.document` | `document_column` (when set) |
| `chunk.metadata[col]` | Each column in `metadata_columns` |

---

## Security considerations

!!! danger "Never pass user-controlled strings as identifiers"
    `table_or_query`, `content_column`, `id_column`, `document_column`, and
    `metadata_columns` are interpolated directly into SQL as structural
    identifiers (table and column names).  SQLAlchemy cannot parameterise these
    the way it can parameterise values.

    Both `SQLLoader` and `SQLWriter` validate every identifier against a strict
    allowlist (`[A-Za-z_][A-Za-z0-9_$]*`) at construction time and raise
    `ValueError` on any value that contains SQL metacharacters.  This catches
    misconfiguration early, but **the best protection is to use only
    hard-coded, developer-controlled strings** — never values derived from
    user input or LLM output.

    For dynamic row filtering, use a parameterised `SELECT` query:

    ```python
    # Safe: user_id is a bound parameter, not an identifier
    loader = SQLLoader(
        connection_string,
        table_or_query="SELECT id, body FROM documents WHERE user_id = :uid",
        content_column="body",
    )
    # Execute with bound parameter via your engine directly, then pass chunks as needed.
    ```

    For connection strings, prefer environment variables or a secrets manager
    over hard-coded passwords:

    ```python
    import os
    loader = SQLLoader(os.environ["DATABASE_URL"], "documents", "body")
    ```
