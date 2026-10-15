# Azure Blob Storage

`AzureBlobLoader` fetches blobs from an Azure Blob Storage container and returns them as `Document` objects (`railtracks.retrieval.models.Document`) containing UTF-8 decoded content, a `source` URI, and provider metadata (`account_url`, `container`, `blob_name`).

## Installation

```bash
pip install railtracks[azure-blob]
```

```bash
uv add railtracks[azure-blob]
```

## Authentication

Authentication defaults to **`DefaultAzureCredential`**, which automatically resolves credentials from the following sources (in order):

1. Environment variables (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_SECRET`)
1. Workload identity (Kubernetes)
1. Managed identity (Azure-hosted compute)
1. Azure CLI (`az login`)
1. Azure PowerShell / Visual Studio / IntelliJ

Pass an explicit `credential` to override.

Prefer managed identity over connection strings

Managed identity is the recommended authentication method for Azure-hosted workloads — it requires no secrets and rotates automatically. Avoid embedding storage account keys or SAS tokens in source code; store them in Azure Key Vault or environment variables instead.

## Basic usage

```python
from railtracks.retrieval.loaders import AzureBlobLoader

# DefaultAzureCredential resolves credentials automatically
# (env vars, managed identity, Azure CLI, ...)
loader = AzureBlobLoader(
    "https://myaccount.blob.core.windows.net",
    "my-container",
)

documents = loader.load()

for doc in documents:
    print(doc.source, "->", doc.content[:80])
```

## Load by prefix

```python
from railtracks.retrieval.loaders import AzureBlobLoader

# Load only blobs whose names begin with "reports/2025/"
loader = AzureBlobLoader(
    "https://myaccount.blob.core.windows.net",
    "my-container",
    prefix="reports/2025/",
)
documents = loader.load()
```

## Load specific blobs

```python
from railtracks.retrieval.loaders import AzureBlobLoader

loader = AzureBlobLoader(
    "https://myaccount.blob.core.windows.net",
    "my-container",
    keys=["policy.txt", "faq.txt", "onboarding/welcome.txt"],
)
documents = loader.load()
```

## Async usage

```python
import asyncio
from railtracks.retrieval.loaders import AzureBlobLoader

async def load_azure_documents():
    loader = AzureBlobLoader(
        "https://myaccount.blob.core.windows.net",
        "my-container",
        prefix="reports/",
    )
    return await loader.aload()

documents = asyncio.run(load_azure_documents())
```

Async is thread-backed

`aload()` and `astream()` run the synchronous `azure-storage-blob` client on a thread-pool thread via `asyncio.to_thread()`. This is correct for most workloads; for very high concurrency consider the async Azure SDK (`azure.storage.blob.aio`).

## Override credentials

**SAS token**

```python
from azure.core.credentials import AzureSasCredential
from railtracks.retrieval.loaders import AzureBlobLoader

loader = AzureBlobLoader(
    "https://myaccount.blob.core.windows.net",
    "my-container",
    credential=AzureSasCredential("<your-sas-token>"),
)
documents = loader.load()
```

**System-assigned or user-assigned managed identity**

```python
from azure.identity import ManagedIdentityCredential
from railtracks.retrieval.loaders import AzureBlobLoader

# Pin to a specific user-assigned managed identity via its client ID
loader = AzureBlobLoader(
    "https://myaccount.blob.core.windows.net",
    "my-container",
    credential=ManagedIdentityCredential(client_id="<client-id>"),
)
documents = loader.load()
```

## Document fields

Each returned `Document` carries:

| Field / metadata key      | Value                                                                       |
| ------------------------- | --------------------------------------------------------------------------- |
| `Document.source`         | Full blob URL: `https://<account>.blob.core.windows.net/<container>/<blob>` |
| `Document.type`           | Inferred from file extension; defaults to `TEXT`                            |
| `metadata["account_url"]` | Storage account URL                                                         |
| `metadata["container"]`   | Container name                                                              |
| `metadata["blob_name"]`   | Blob name (path within the container)                                       |
