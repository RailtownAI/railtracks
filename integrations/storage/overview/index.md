# Cloud Storage & Database Loaders

Railtracks ships convenience **loaders** for popular cloud storage providers and relational databases.

- **Loaders** fetch data and return it as `Document` objects (`railtracks.retrieval.models.Document`) allowing you to pipe remote data straight into a retrieval pipeline.

## Supported providers

| Provider                                    | Loader            | Install extra            |
| ------------------------------------------- | ----------------- | ------------------------ |
| AWS S3                                      | `S3Loader`        | `railtracks[aws]`        |
| Azure Blob Storage                          | `AzureBlobLoader` | `railtracks[azure-blob]` |
| Google Cloud Storage                        | `GCSLoader`       | `railtracks[gcp]`        |
| SQL (PostgreSQL, Supabase, MySQL, SQLite …) | `SQLLoader`       | `railtracks[sql]`        |

Install any combination:

```bash
pip install "railtracks[aws,gcp,azure-blob,sql]"
```

```bash
uv add "railtracks[aws,gcp,azure-blob,sql]"
```

## Quick Examples

```python
from railtracks.retrieval.loaders import BaseDocumentLoader,S3Loader

loader: BaseDocumentLoader = S3Loader("my-bucket", region_name="us-east-1")

# Load every object in the bucket as Document instances
documents = loader.load()

for doc in documents:
    print(doc.source, "->", doc.content[:80])
```

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

```python
from railtracks.retrieval.loaders import GCSLoader

# Application Default Credentials resolve automatically
# (GOOGLE_APPLICATION_CREDENTIALS, gcloud auth, Workload Identity ...)
loader = GCSLoader("my-bucket", project="my-gcp-project")

documents = loader.load()

for doc in documents:
    print(doc.source, "->", doc.content[:80])
```

```python
from railtracks.retrieval.loaders import SQLLoader

loader = SQLLoader(
    "postgresql+psycopg2://user:pass@db.example.com:5432/mydb",
    table_or_query="documents",
    content_column="body",
    metadata_columns=["title", "author", "created_at"],
    id_column="id",
)
documents = loader.load()

for doc in documents:
    print(doc.metadata["title"], "->", doc.content[:80])
```

## Feeding documents into a RAG pipeline

All loaders return the same `Document` type used by the retrieval module, making it trivial to build a full load → chunk → embed → retrieve → answer pipeline:

```python
import railtracks as rt
from railtracks.retrieval import RetrievalRuntime
from railtracks.retrieval.runtime import BatchIngested, DocumentFailed, DocumentSkipped
from railtracks.retrieval.chunking import SentenceChunker
from railtracks.retrieval.embedding import OpenAIEmbedding, EmbeddingFailure
from railtracks.retrieval.stores import VectorStore, InMemoryVectorBackend
from railtracks.retrieval.loaders import S3Loader

# Connect to/Create your Runtime
runtime = RetrievalRuntime(
        chunker=SentenceChunker(chunk_size=5, overlap=1),
        embedder=OpenAIEmbedding(model="text-embedding-3-small"),
        store=VectorStore(InMemoryVectorBackend()),
        batch_size=64,
)

# 1. Load documents from S3
loader = S3Loader("my-knowledge-bucket", prefix="docs/", region_name="us-east-1")
async def create():
    async for event in runtime.ingest(loader):
        match event:
            case BatchIngested(document_id=did, embedded_chunks=ch, batch_index=i):
                print(f"  + doc={str(did)[:8]} batch={i} chunks={len(ch)}")
            case EmbeddingFailure(errors=errs):
                print(f"  ! embedding failed: {errs[0]}")
            case DocumentFailed(document_id=did):
                print(f"  ! doc {str(did)[:8]} partially failed")
            case DocumentSkipped(source=src):
                print(f"  ~ skipped (unchanged): {src}")

# 3. Expose retrieval as an agent tool
@rt.function_node
async def search_knowledge_base(query: str) -> str:
    """Search the internal knowledge base for relevant information."""
    results = await runtime.retrieve(query, top_k=5)
    return "\n\n".join(r.chunk.content for r in results.chunks)

# 4. Build the agent
KnowledgeAgent = rt.agent_node(
    name="KnowledgeAgent",
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    system_message="You are a helpful assistant. Use the knowledge base to answer questions.",
    tool_nodes=[search_knowledge_base],
)

flow = rt.Flow("knowledge-flow", entry_point=KnowledgeAgent)
response = flow.invoke("What is our remote work policy?")
```

## Async support

Loaders implement `astream()` (the streaming primitive on `BaseDocumentLoader`) plus `aload()`, for use in `async` pipelines:

```python
documents = await loader.aload()

# Or stream documents as they download
async for doc in loader.astream():
    ...
```

The async methods delegate to `asyncio.to_thread()`, so they are non-blocking from the caller's perspective while the underlying SDK call runs on a thread-pool thread.

## Selecting what to load

Loaders accept their scope in the constructor:

- `prefix=` — load every object/blob/row whose key starts with the prefix (recursive — nested "folders" such as `docs/A/B.txt` are included).
- `keys=` — load an explicit list of keys (S3/GCS/Azure) or `id_column` values (SQL).

```python
S3Loader("my-bucket", prefix="docs/")
S3Loader("my-bucket", keys=["a.txt", "nested/b.txt"])
```

Next steps

- [AWS S3](https://docs.railtracks.org/integrations/storage/s3/index.md) · [Azure Blob Storage](https://docs.railtracks.org/integrations/storage/azure_blob/index.md) · [Google Cloud Storage](https://docs.railtracks.org/integrations/storage/gcs/index.md) · [SQL](https://docs.railtracks.org/integrations/storage/sql/index.md)
