# Cloud Storage & Database Loaders / Writers

Railtracks ships first-class **loaders** and **writers** for popular cloud
storage providers and relational databases.

- **Loaders** fetch documents and return them as
  [`Chunk`](../../rag/vector_stores/vector_store_info.md) objects — pipe remote
  data straight into a vector store or agent without any glue code.
- **Writers** persist `Chunk` objects (or raw text) back to the same providers —
  close the loop by saving AI-generated content to storage.

## Supported providers

| Provider | Loader | Writer | Install extra |
|---|---|---|---|
| AWS S3 | `S3Loader` | `S3Writer` | `railtracks[aws]` |
| Azure Blob Storage | `AzureBlobLoader` | `AzureBlobWriter` | `railtracks[azure-blob]` |
| Google Cloud Storage | `GCSLoader` | `GCSWriter` | `railtracks[gcp]` |
| SQL (PostgreSQL, Supabase, MySQL, SQLite …) | `SQLLoader` | `SQLWriter` | `railtracks[sql]` |

Install any combination:

=== "pip"

    ```bash
    pip install "railtracks[aws,gcp,azure-blob,sql]"
    ```

=== "uv"

    ```bash
    uv add "railtracks[aws,gcp,azure-blob,sql]"
    ```

## Loading — quick examples

=== "AWS S3"

    ```python
    --8<-- "docs/scripts/storage_loaders.py:s3_basic"
    ```

=== "Azure Blob"

    ```python
    --8<-- "docs/scripts/storage_loaders.py:azure_basic"
    ```

=== "Google Cloud Storage"

    ```python
    --8<-- "docs/scripts/storage_loaders.py:gcs_basic"
    ```

=== "SQL / Database"

    ```python
    --8<-- "docs/scripts/storage_loaders.py:sql_basic_postgres"
    ```

## Writing — quick examples

=== "AWS S3"

    ```python
    --8<-- "docs/scripts/storage_writers.py:s3_write_basic"
    ```

=== "Azure Blob"

    ```python
    --8<-- "docs/scripts/storage_writers.py:azure_write_basic"
    ```

=== "Google Cloud Storage"

    ```python
    --8<-- "docs/scripts/storage_writers.py:gcs_write_basic"
    ```

=== "SQL / Database"

    ```python
    --8<-- "docs/scripts/storage_writers.py:sql_write_basic"
    ```

## Feeding chunks into a RAG pipeline

All loaders return the same `Chunk` type that `ChromaVectorStore.upsert()` accepts,
making it trivial to build a full load → index → retrieve → answer pipeline:

```python
--8<-- "docs/scripts/storage_loaders.py:pipeline_s3_to_rag"
```

## Load → Generate → Write back

Writers make it easy to persist AI-generated content alongside source data:

```python
--8<-- "docs/scripts/storage_writers.py:pipeline_generate_and_write"
```

## Async support

Every loader and writer exposes async variants (`aload`, `aload_keys`, `awrite`,
`awrite_key`) that are safe to use in `async` agent pipelines:

```python
chunks = await loader.aload(prefix="reports/2024/")
uris   = await writer.awrite(chunks, prefix="summaries/")
```

The async methods delegate to `asyncio.to_thread()`, so they are non-blocking
from the caller's perspective while the underlying SDK call runs on a thread-pool
thread.

## Key derivation for writers

When writing `Chunk` objects, the storage key (S3 key, GCS object name, blob
name, SQL id) is derived in this order:

1. Return value of `key_fn(chunk)` — if `key_fn` is provided
2. `chunk.id` — if set
3. `chunk.document` — if set
4. A freshly generated UUID4 — as a last resort

Pass `key_fn` to take full control of the naming scheme:

```python
writer = S3Writer("my-bucket", key_fn=lambda c: f"docs/{c.id}.txt")
```

!!! tip "Next steps"
    - [AWS S3](s3.md) · [Azure Blob Storage](azure_blob.md) · [Google Cloud Storage](gcs.md) · [SQL](sql.md)
    - [Cloud Storage Loaders Tutorial](../../tutorials/walkthroughs/storage_loaders_tutorial.md)
