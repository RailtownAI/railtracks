# SQL / Relational Databases

`SQLLoader` reads rows from any **SQLAlchemy-compatible relational database**
and returns them as `Document` objects
(`railtracks.retrieval.models.Document`). Works with PostgreSQL, Supabase,
MySQL, SQLite, and more.

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
    Filtering by `keys=` requires `id_column` to be set when constructing the
    loader.

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
    documents = loader.load()
finally:
    loader.close()

# Context-manager (preferred)
with SQLLoader(connection_string, "documents", "body") as loader:
    documents = loader.load()
```

## Async usage

```python
--8<-- "docs/scripts/storage_loaders.py:sql_async"
```

!!! note "Async is thread-backed"
    `aload()` and `astream()` run the synchronous SQLAlchemy driver on a
    thread-pool thread via `asyncio.to_thread()`.  This works correctly but
    occupies a thread for the full duration of the query.  For very
    high-concurrency workloads consider wiring up a true async engine
    (e.g. `asyncpg` with `sqlalchemy.ext.asyncio`) and passing it via the
    `engine` parameter.

## Document fields

Each returned `Document` carries:

| Field / metadata key | Value |
|---|---|
| `Document.source` | Value of `source_column` (if set), otherwise the value of `id_column`, otherwise the `table_or_query` string |
| `Document.type` | `DocumentType.TEXT` |
| `metadata[<col>]` | One entry per column listed in `metadata_columns` |

When `metadata_columns` is `None`, all columns except `content_column` and
`id_column` are included automatically.

## Full RAG pipeline example

```python
--8<-- "docs/scripts/storage_loaders.py:pipeline_sql_to_rag"
```

---

## Security considerations

!!! danger "Never pass user-controlled strings as identifiers"
    `table_or_query`, `content_column`, `id_column`, `source_column`, and
    `metadata_columns` are interpolated directly into SQL as structural
    identifiers (table and column names).  SQLAlchemy cannot parameterise these
    the way it can parameterise values.

    `SQLLoader` validates every identifier against a strict allowlist
    (`[A-Za-z_][A-Za-z0-9_$]*`) at construction time and raises
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
