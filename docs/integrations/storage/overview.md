# Cloud Storage & Database Loaders

Railtracks ships first-class **loaders** for popular cloud storage providers
and relational databases.

- **Loaders** fetch data and return it as `Document` objects
  (`railtracks.retrieval.models.Document`) — pipe remote data straight into a
  retrieval pipeline without any glue code.

## Supported providers

| Provider | Loader | Install extra |
|---|---|---|
| AWS S3 | `S3Loader` | `railtracks[aws]` |
| Azure Blob Storage | `AzureBlobLoader` | `railtracks[azure-blob]` |
| Google Cloud Storage | `GCSLoader` | `railtracks[gcp]` |
| SQL (PostgreSQL, Supabase, MySQL, SQLite …) | `SQLLoader` | `railtracks[sql]` |

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

## Feeding documents into a RAG pipeline

All loaders return the same `Document` type used by the retrieval module,
making it trivial to build a full load → chunk → embed → retrieve → answer
pipeline:

```python
--8<-- "docs/scripts/storage_loaders.py:pipeline_s3_to_rag"
```

## Async support

Loaders implement `astream()` (the streaming primitive on
`BaseDocumentLoader`) plus `aload()`, for use in `async` pipelines:

```python
documents = await loader.aload()

# Or stream documents as they download
async for doc in loader.astream():
    ...
```

The async methods delegate to `asyncio.to_thread()`, so they are non-blocking
from the caller's perspective while the underlying SDK call runs on a
thread-pool thread.

## Selecting what to load

Loaders accept their scope in the constructor:

- `prefix=` — load every object/blob/row whose key starts with the prefix
  (recursive — nested "folders" such as `docs/A/B.txt` are included).
- `keys=` — load an explicit list of keys (S3/GCS/Azure) or `id_column`
  values (SQL).

```python
S3Loader("my-bucket", prefix="docs/")
S3Loader("my-bucket", keys=["a.txt", "nested/b.txt"])
```

!!! tip "Next steps"
    - [AWS S3](s3.md) · [Azure Blob Storage](azure_blob.md) · [Google Cloud Storage](gcs.md) · [SQL](sql.md)
    - [Cloud Storage Loaders Tutorial](../../tutorials/walkthroughs/storage_loaders_tutorial.md)
