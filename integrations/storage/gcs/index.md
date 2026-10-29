# Google Cloud Storage

`GCSLoader` fetches objects from a GCS bucket and returns them as `Document` objects (`railtracks.retrieval.models.Document`) containing the object's text, a `source` URI, and provider metadata (`bucket`, `name`). PDFs are parsed into text; see [PDFs and other binary objects](#pdfs-and-other-binary-objects).

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

## PDFs and other binary objects

Objects whose name ends in `.pdf`, in any case (`REPORT.PDF` too), are parsed with the same logic as [`PyPDFLoader`](https://docs.railtracks.org/retrieval/components/ingestion/methods/#pypdfloader), which needs the `pdf` extra (`pip install railtracks[pdf]`). Without it, text-only loads still work, and a load that includes a PDF raises an `ImportError` naming the extra before any object is downloaded.

By default each non-empty page becomes its own `Document`, with `page`, `total_pages` and `file_type` added to the metadata above. Pass `pdf_breakdown_strategy="paragraph"` or `"document"` to split PDFs the way `PyPDFLoader` does.

An object named `.txt`, `.md`, `.markdown`, `.csv`, `.json` or `.jsonl` that is not valid text in `encoding` raises a `ValueError`, since that usually means `encoding` is wrong. Any other object that is not valid text, such as an image or a Word file, is skipped with a warning instead of stopping the load.

## Document fields

Each returned `Document` carries:

| Field / metadata key      | Value                                                                      |
| ------------------------- | -------------------------------------------------------------------------- |
| `Document.source`         | `gs://<bucket>/<name>`                                                     |
| `Document.type`           | Inferred from file extension; defaults to `TEXT`                           |
| `metadata["bucket"]`      | GCS bucket name                                                            |
| `metadata["name"]`        | Object name (path within the bucket)                                       |
| `metadata["page"]`        | PDFs only: 1-based page number (`page` and `paragraph` strategies)         |
| `metadata["paragraph"]`   | PDFs only: 1-based paragraph number within the page (`paragraph` strategy) |
| `metadata["total_pages"]` | PDFs only: number of pages in the PDF                                      |
| `metadata["file_type"]`   | PDFs only: `.pdf`                                                          |
