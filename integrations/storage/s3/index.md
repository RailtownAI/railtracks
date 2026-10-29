# AWS S3

`S3Loader` fetches objects from an S3 bucket and returns them as `Document` objects (`railtracks.retrieval.models.Document`) containing the object's text, a `source` URI, and provider metadata (`bucket`, `key`). PDFs are parsed into text; see [PDFs and other binary objects](#pdfs-and-other-binary-objects).

## Installation

```bash
pip install railtracks[aws]
```

```bash
uv add railtracks[aws]
```

## Authentication

Credentials follow **boto3's standard resolution chain** — no explicit configuration needed in most environments:

1. Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`)
1. Shared credentials file (`~/.aws/credentials`)
1. AWS config file (`~/.aws/config`)
1. IAM role attached to an EC2 instance / ECS task / Lambda function

Pass explicit credentials to the constructor to override the chain.

Prefer IAM roles and environment variables over hard-coded credentials

Never embed AWS keys directly in source code. Use environment variables, AWS Secrets Manager, or an IAM instance profile wherever possible.

## Basic usage

```python
from railtracks.retrieval.loaders import BaseDocumentLoader,S3Loader

loader: BaseDocumentLoader = S3Loader("my-bucket", region_name="us-east-1")

# Load every object in the bucket as Document instances
documents = loader.load()

for doc in documents:
    print(doc.source, "->", doc.content[:80])
```

## Load by prefix

```python
from railtracks.retrieval.loaders import S3Loader

# Load only objects under the "knowledge-base/" prefix
loader = S3Loader("my-bucket", prefix="knowledge-base/", region_name="us-east-1")
documents = loader.load()
```

## Load specific keys

```python
from railtracks.retrieval.loaders import S3Loader

# Load a specific set of objects by key
loader = S3Loader(
    "my-bucket",
    keys=["policy.txt", "faq.txt", "onboarding/welcome.txt"],
)
documents = loader.load()
```

## Async usage

```python
import asyncio
from railtracks.retrieval.loaders import S3Loader

async def load_s3_documents():
    loader = S3Loader("my-bucket", prefix="docs/", region_name="us-east-1")

    # Stream documents as they download
    streamed = [doc async for doc in loader.astream()]

    # Or collect everything into a list
    all_docs = await loader.aload()
    return streamed + all_docs

documents = asyncio.run(load_s3_documents())
```

Async is thread-backed

`aload()` and `astream()` run the synchronous boto3 client on a thread-pool thread via `asyncio.to_thread()`. This is correct for most workloads; for very high concurrency consider `aioboto3`.

## Override credentials

```python
from railtracks.retrieval.loaders import S3Loader

loader = S3Loader(
    "my-bucket",
    aws_access_key_id="AKIA...",
    aws_secret_access_key="...",
    region_name="eu-west-1",
)
documents = loader.load()
```

## S3-compatible services (MinIO, LocalStack …)

```python
from railtracks.retrieval.loaders import S3Loader

# Works with any S3-compatible service (MinIO, LocalStack, Ceph ...)
loader = S3Loader(
    "my-bucket",
    endpoint_url="http://localhost:9000",
    aws_access_key_id="minioadmin",
    aws_secret_access_key="minioadmin",
)
documents = loader.load()
```

## PDFs and other binary objects

Objects whose name ends in `.pdf`, in any case (`REPORT.PDF` too), are parsed with the same logic as [`PyPDFLoader`](https://docs.railtracks.org/retrieval/components/ingestion/methods/#pypdfloader), which needs the `pdf` extra (`pip install railtracks[pdf]`). Without it, text-only loads still work, and a load that includes a PDF raises an `ImportError` naming the extra before any object is downloaded.

By default each non-empty page becomes its own `Document`, with `page`, `total_pages` and `file_type` added to the metadata above. Pass `pdf_breakdown_strategy="paragraph"` or `"document"` to split PDFs the way `PyPDFLoader` does.

An object named `.txt`, `.md`, `.markdown`, `.csv`, `.json` or `.jsonl` that is not valid text in `encoding` raises a `ValueError`, since that usually means `encoding` is wrong. Any other object that is not valid text, such as an image or a Word file, is skipped with a warning instead of stopping the load.

## Document fields

Each returned `Document` carries:

| Field / metadata key      | Value                                                                                 |
| ------------------------- | ------------------------------------------------------------------------------------- |
| `Document.source`         | `s3://<bucket>/<key>`                                                                 |
| `Document.type`           | Inferred from the object's file extension (`.md`, `.csv`, ...) — falls back to `TEXT` |
| `metadata["bucket"]`      | S3 bucket name                                                                        |
| `metadata["key"]`         | Object key (path)                                                                     |
| `metadata["page"]`        | PDFs only: 1-based page number (`page` and `paragraph` strategies)                    |
| `metadata["paragraph"]`   | PDFs only: 1-based paragraph number within the page (`paragraph` strategy)            |
| `metadata["total_pages"]` | PDFs only: number of pages in the PDF                                                 |
| `metadata["file_type"]`   | PDFs only: `.pdf`                                                                     |
