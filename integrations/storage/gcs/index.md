# Google Cloud Storage

`GCSLoader` fetches objects from a GCS bucket and returns them as `Document` objects (`railtracks.retrieval.models.Document`) containing UTF-8 decoded content, a `source` URI, and provider metadata (`bucket`, `name`).

## Installation

```bash
pip install railtracks[gcp]
```

```bash
uv add railtracks[gcp]
```

## Authentication

Authentication uses **Application Default Credentials (ADC)** by default:

1. `GOOGLE_APPLICATION_CREDENTIALS` environment variable (path to a service-account JSON)
1. `gcloud auth application-default login` (developer workstation)
1. Workload Identity / attached service account (GCE, GKE, Cloud Run, Cloud Functions …)

Pass explicit `credentials` to override ADC.

Prefer Workload Identity over service-account key files

Service-account JSON key files are long-lived credentials that require manual rotation. On GCP-hosted compute, Workload Identity or attached service accounts are more secure and require zero key management.

## Basic usage

```python
from railtracks.retrieval.loaders import GCSLoader

# Application Default Credentials resolve automatically
# (GOOGLE_APPLICATION_CREDENTIALS, gcloud auth, Workload Identity ...)
loader = GCSLoader("my-bucket", project="my-gcp-project")

documents = loader.load()

for doc in documents:
    print(doc.source, "->", doc.content[:80])
```

## Load by prefix

```python
from railtracks.retrieval.loaders import GCSLoader

loader = GCSLoader("my-bucket", prefix="knowledge-base/")
documents = loader.load()
```

## Load specific objects

```python
from railtracks.retrieval.loaders import GCSLoader

loader = GCSLoader(
    "my-bucket",
    keys=["policy.txt", "faq.txt", "onboarding/welcome.txt"],
)
documents = loader.load()
```

## Async usage

```python
import asyncio
from railtracks.retrieval.loaders import GCSLoader

async def load_gcs_documents():
    loader = GCSLoader("my-bucket", project="my-gcp-project", prefix="docs/")
    return await loader.aload()

documents = asyncio.run(load_gcs_documents())
```

Async is thread-backed

`aload()` and `astream()` run the synchronous `google-cloud-storage` client on a thread-pool thread via `asyncio.to_thread()`. This is correct for most workloads.

## Override credentials (service account key file)

```python
from google.oauth2 import service_account
from railtracks.retrieval.loaders import GCSLoader

credentials = service_account.Credentials.from_service_account_file(
    "/path/to/service-account.json",
    scopes=["https://www.googleapis.com/auth/cloud-platform"],
)
loader = GCSLoader("my-bucket", credentials=credentials)
documents = loader.load()
```

## Document fields

Each returned `Document` carries:

| Field / metadata key | Value                                            |
| -------------------- | ------------------------------------------------ |
| `Document.source`    | `gs://<bucket>/<name>`                           |
| `Document.type`      | Inferred from file extension; defaults to `TEXT` |
| `metadata["bucket"]` | GCS bucket name                                  |
| `metadata["name"]`   | Object name (path within the bucket)             |
