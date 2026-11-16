# Azure Blob Storage

`AzureBlobLoader` fetches blobs from an Azure Blob Storage container and returns them as `Document` objects (`railtracks.retrieval.models.Document`) containing the blob's text, a `source` URI, and provider metadata (`account_url`, `container`, `blob_name`). PDFs are parsed into text; see [PDFs and other binary objects](#pdfs-and-other-binary-objects).

## Installation

=== "pip"

    ```bash
    pip install railtracks[azure-blob]
    ```

=== "uv"

    ```bash
    uv add railtracks[azure-blob]
    ```

## Authentication

Authentication defaults to **`DefaultAzureCredential`**, which automatically resolves
credentials from the following sources (in order):

1. Environment variables (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_SECRET`)
2. Workload identity (Kubernetes)
3. Managed identity (Azure-hosted compute)
4. Azure CLI (`az login`)
5. Azure PowerShell / Visual Studio / IntelliJ

Pass an explicit `credential` to override.

!!! tip "Prefer managed identity over connection strings"
    Managed identity is the recommended authentication method for Azure-hosted
    workloads — it requires no secrets and rotates automatically.  Avoid
    embedding storage account keys or SAS tokens in source code; store them
    in Azure Key Vault or environment variables instead.

## Basic usage

```python
--8<-- "docs/scripts/integrations/storage_loaders.py:azure_basic"
```

## Load by prefix

```python
--8<-- "docs/scripts/integrations/storage_loaders.py:azure_prefix"
```

## Load specific blobs

```python
--8<-- "docs/scripts/integrations/storage_loaders.py:azure_load_keys"
```

## Async usage

```python
--8<-- "docs/scripts/integrations/storage_loaders.py:azure_async"
```

!!! note "Async is thread-backed"
    `aload()` and `astream()` run the synchronous `azure-storage-blob`
    client on a thread-pool thread via `asyncio.to_thread()`.  This is correct
    for most workloads; for very high concurrency consider the async Azure SDK
    (`azure.storage.blob.aio`).

## Override credentials

**SAS token**

```python
--8<-- "docs/scripts/integrations/storage_loaders.py:azure_sas"
```

**System-assigned or user-assigned managed identity**

```python
--8<-- "docs/scripts/integrations/storage_loaders.py:azure_managed_identity"
```

## PDFs and other binary objects

Objects whose name ends in `.pdf`, in any case (`REPORT.PDF` too), are parsed with the same logic as [`PyPDFLoader`](../../retrieval/components/ingestion/methods.md#pypdfloader), which needs the `pdf` extra (`pip install railtracks[pdf]`). Without it, text-only loads still work, and a load that includes a PDF raises an `ImportError` naming the extra before any object is downloaded.

By default each non-empty page becomes its own `Document`, with `page`, `total_pages` and `file_type` added to the metadata above. Pass `pdf_breakdown_strategy="paragraph"` or `"document"` to split PDFs the way `PyPDFLoader` does.

An object named `.txt`, `.md`, `.markdown`, `.csv`, `.json` or `.jsonl` that is not valid text in `encoding` (which usually means `encoding` is wrong), a corrupt PDF, or an object that fails to download is yielded as a `LoadFailure` and the remaining objects still load; `RetrievalRuntime` reports it as a `DocumentFailed` with `stage="load"`, while `load()` and `aload()` raise its error. Any other object that is not valid text, such as an image or a Word file, is skipped with a warning.

## Document fields

Each returned `Document` carries:

| Field / metadata key | Value |
|---|---|
| `Document.source` | Full blob URL: `https://<account>.blob.core.windows.net/<container>/<blob>` |
| `Document.type` | Inferred from file extension; defaults to `TEXT` |
| `metadata["account_url"]` | Storage account URL |
| `metadata["container"]` | Container name |
| `metadata["blob_name"]` | Blob name (path within the container) |
| `metadata["page"]` | PDFs only: 1-based page number (`page` and `paragraph` strategies) |
| `metadata["paragraph"]` | PDFs only: 1-based paragraph number within the page (`paragraph` strategy) |
| `metadata["total_pages"]` | PDFs only: number of pages in the PDF |
| `metadata["file_type"]` | PDFs only: `.pdf` |
