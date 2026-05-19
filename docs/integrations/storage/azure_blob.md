# Azure Blob Storage

`AzureBlobLoader` fetches blobs from an Azure Blob Storage container and returns them as
[`Chunk`](../../rag/vector_stores/vector_store_info.md) objects containing
UTF-8 decoded content plus source metadata (`source`, `account_url`, `container`,
`blob_name`).

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
--8<-- "docs/scripts/storage_loaders.py:azure_basic"
```

## Load by prefix

```python
--8<-- "docs/scripts/storage_loaders.py:azure_prefix"
```

## Load specific blobs

```python
--8<-- "docs/scripts/storage_loaders.py:azure_load_keys"
```

## Async usage

```python
--8<-- "docs/scripts/storage_loaders.py:azure_async"
```

!!! note "Async is thread-backed"
    `aload()` and `aload_keys()` run the synchronous `azure-storage-blob`
    client on a thread-pool thread via `asyncio.to_thread()`.  This is correct
    for most workloads; for very high concurrency consider the async Azure SDK
    (`azure.storage.blob.aio`).

## Override credentials

**SAS token**

```python
--8<-- "docs/scripts/storage_loaders.py:azure_sas"
```

**System-assigned or user-assigned managed identity**

```python
--8<-- "docs/scripts/storage_loaders.py:azure_managed_identity"
```

## Chunk metadata

Each returned `Chunk` carries:

| Key | Value |
|---|---|
| `source` | Full blob URL: `https://<account>.blob.core.windows.net/<container>/<blob>` |
| `account_url` | Storage account URL |
| `container` | Container name |
| `blob_name` | Blob name (path within the container) |

## Full RAG pipeline example

```python
--8<-- "docs/scripts/storage_loaders.py:pipeline_azure_to_rag"
```

---

## Writing to Azure Blob Storage

`AzureBlobWriter` uploads text content to a blob container.  Existing blobs at
the same name are overwritten.

### Basic write

```python
--8<-- "docs/scripts/storage_writers.py:azure_write_basic"
```

### SAS token credential

```python
--8<-- "docs/scripts/storage_writers.py:azure_write_sas"
```

### Async write

```python
--8<-- "docs/scripts/storage_writers.py:azure_write_async"
```
