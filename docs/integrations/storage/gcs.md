# Google Cloud Storage

`GCSLoader` fetches objects from a GCS bucket and returns them as `Document` objects (`railtracks.retrieval.models.Document`) containing the object's text, a `source` URI, and provider metadata (`bucket`, `name`). PDFs are parsed into text; see [PDFs and other binary objects](#pdfs-and-other-binary-objects).

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
--8<-- "docs/scripts/integrations/storage_loaders.py:gcs_basic"
```

## Load by prefix

```python
--8<-- "docs/scripts/integrations/storage_loaders.py:gcs_prefix"
```

## Load specific objects

```python
--8<-- "docs/scripts/integrations/storage_loaders.py:gcs_load_keys"
```

## Async usage

```python
--8<-- "docs/scripts/integrations/storage_loaders.py:gcs_async"
```

!!! note "Async is thread-backed"
    `aload()` and `astream()` run the synchronous `google-cloud-storage`
    client on a thread-pool thread via `asyncio.to_thread()`.  This is correct
    for most workloads.

## Override credentials (service account key file)

```python
--8<-- "docs/scripts/integrations/storage_loaders.py:gcs_service_account"
```

## PDFs and other binary objects

Objects whose name ends in `.pdf` are parsed with the same logic as [`PyPDFLoader`](../../retrieval/components/ingestion/methods.md#pypdfloader), which needs the `pdf` extra (`pip install railtracks[pdf]`). Without it, text objects still load, and the first PDF raises an `ImportError` naming the extra.

By default each non-empty page becomes its own `Document`, with `page`, `total_pages` and `file_type` added to the metadata above. Pass `pdf_breakdown_strategy="paragraph"` or `"document"` to split PDFs the way `PyPDFLoader` does.

Any other object that is not valid text in `encoding`, such as an image or a Word file, is skipped with a warning instead of stopping the load.

## Document fields

Each returned `Document` carries:

| Field / metadata key | Value |
|---|---|
| `Document.source` | `gs://<bucket>/<name>` |
| `Document.type` | Inferred from file extension; defaults to `TEXT` |
| `metadata["bucket"]` | GCS bucket name |
| `metadata["name"]` | Object name (path within the bucket) |
