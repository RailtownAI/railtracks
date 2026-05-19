# Google Cloud Storage

`GCSLoader` fetches objects from a GCS bucket and returns them as
[`Chunk`](../../rag/vector_stores/vector_store_info.md) objects containing
UTF-8 decoded content plus source metadata (`source`, `bucket`, `name`).

## Installation

=== "pip"

    ```bash
    pip install railtracks[gcp]
    ```

=== "uv"

    ```bash
    uv add railtracks[gcp]
    ```

## Authentication

Authentication uses **Application Default Credentials (ADC)** by default:

1. `GOOGLE_APPLICATION_CREDENTIALS` environment variable (path to a service-account JSON)
2. `gcloud auth application-default login` (developer workstation)
3. Workload Identity / attached service account (GCE, GKE, Cloud Run, Cloud Functions …)

Pass explicit `credentials` to override ADC.

!!! tip "Prefer Workload Identity over service-account key files"
    Service-account JSON key files are long-lived credentials that require
    manual rotation.  On GCP-hosted compute, Workload Identity or attached
    service accounts are more secure and require zero key management.

## Basic usage

```python
--8<-- "docs/scripts/storage_loaders.py:gcs_basic"
```

## Load by prefix

```python
--8<-- "docs/scripts/storage_loaders.py:gcs_prefix"
```

## Load specific objects

```python
--8<-- "docs/scripts/storage_loaders.py:gcs_load_keys"
```

## Async usage

```python
--8<-- "docs/scripts/storage_loaders.py:gcs_async"
```

!!! note "Async is thread-backed"
    `aload()` and `aload_keys()` run the synchronous `google-cloud-storage`
    client on a thread-pool thread via `asyncio.to_thread()`.  This is correct
    for most workloads.

## Override credentials (service account key file)

```python
--8<-- "docs/scripts/storage_loaders.py:gcs_service_account"
```

## Chunk metadata

Each returned `Chunk` carries:

| Key | Value |
|---|---|
| `source` | `gs://<bucket>/<name>` |
| `bucket` | GCS bucket name |
| `name` | Object name (path within the bucket) |

## Full RAG pipeline example

```python
--8<-- "docs/scripts/storage_loaders.py:pipeline_gcs_to_rag"
```

---

## Writing to GCS

`GCSWriter` uploads text content to a GCS bucket.  Existing objects at the
same name are overwritten.

### Basic write

```python
--8<-- "docs/scripts/storage_writers.py:gcs_write_basic"
```

### Service account credentials

```python
--8<-- "docs/scripts/storage_writers.py:gcs_write_service_account"
```

### Async write

```python
--8<-- "docs/scripts/storage_writers.py:gcs_write_async"
```
