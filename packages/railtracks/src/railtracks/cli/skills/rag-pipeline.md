# Build a Railtracks RAG Pipeline

The user wants to build a retrieval-augmented generation (RAG) pipeline using the railtracks framework: $ARGUMENTS

## How railtracks retrieval works

The pipeline has two paths:

**Write path (ingestion):** `Loader → Chunker → Embedder → VectorStore`
**Read path (retrieval):** `query → Embedder → VectorStore.search → RetrievalResult`

`RetrievalRuntime` orchestrates both paths. It takes a chunker, embedder, and store at construction time, then exposes `ingest_all()` / `ingest()` for writes and `retrieve()` for reads.

### Core data flow
| Stage | Input | Output |
|-------|-------|--------|
| Loader | source (file, URL, dataset) | `Document` |
| Chunker | `Document` | `Chunk` |
| Embedder | `Chunk.content` | `EmbeddedChunk` |
| Store | `EmbeddedChunk` | stored `StoreEntry` |
| Retrieve | query string | `RetrievalResult` (ranked `RetrievedChunk` list) |

---

## Component reference

### Loaders
```python
from railtracks.retrieval.loaders import (
    TextLoader,                  # .txt / .md files
    CSVLoader,                   # rows → documents; configure content_col, metadata_cols
    JSONLoader,                  # .json / .jsonl files
    PyPDFLoader,                 # PDF; strategy="page" (default) or "document"
    HuggingFaceDatasetLoader,    # HF Hub datasets; pass dataset_name, split, text_column
    LangChainLoaderAdapter,      # wrap any LangChain document loader
)
```

### Chunkers
```python
from railtracks.retrieval.chunking import (
    RecursiveCharacterChunker,  # general text; chunk_size (chars), overlap
    MarkdownHeaderChunker,      # heading-aware splits for .md content
    SentenceChunker,            # sentence windows; chunk_size (# sentences), overlap
    SemanticChunker,            # embedding-driven breakpoints; variable chunk size
    FixedTokenChunker,          # hard token budget; chunk_size (tokens), overlap
)
```

### Embedders
```python
from railtracks.retrieval.embedding import (
    OpenAIEmbedding,    # default model: "text-embedding-3-small"
    AzureEmbedding,     # Azure OpenAI routing
    OllamaEmbedding,    # local dev; model, base_url
    LiteLLMEmbedding,   # any LiteLLM-supported provider
)
```

### Store backends
```python
from railtracks.retrieval.stores import (
    VectorStore,              # store implementation; wraps a backend
    InMemoryVectorBackend,    # tests and small corpora; no persistence by default
    ChromaBackend,            # local / persistent / HTTP modes
    ChromaCloudBackend,       # managed Chroma Cloud
    PgvectorBackend,          # Postgres + pgvector; production
)
```

### Installation extras
```
pip install "railtracks[retrieval-core]"   # minimum (no connectors)
pip install "railtracks[retrieval]"        # all connectors
pip install "railtracks[chroma]"           # Chroma only
pip install "railtracks[huggingface]"      # HuggingFace datasets
pip install "railtracks[ocr]"             # PyPDF + OCR (requires Tesseract)
```

---

## Steps

1. **Read the existing code** — check what files already exist. Understand what data source, chunking strategy, and query pattern the user needs before writing anything.
2. **Choose a loader** — match the source type (file, PDF, CSV, HuggingFace dataset, etc.). Ask the user to clarify if not obvious from `$ARGUMENTS`.
3. **Choose a chunker** — default to `RecursiveCharacterChunker` for plain text, `MarkdownHeaderChunker` for structured docs, `SentenceChunker` for narrative text. Use `SemanticChunker` only when chunk boundaries matter semantically.
4. **Choose an embedder** — default to `OpenAIEmbedding()` (text-embedding-3-small). Use `OllamaEmbedding` for local/offline dev.
5. **Choose a backend** — `InMemoryVectorBackend` for demos/tests, `ChromaBackend` for local persistence, `PgvectorBackend` for production.
6. **Construct `RetrievalRuntime`** — pass chunker, embedder, store. Initialize async backends with `await backend.initialize()` or the `ChromaBackend.create()` factory.
7. **Ingest documents** — call `runtime.ingest_all(loader=...)`. Print stats. Handle `documents_failed` gracefully.
8. **Add a retrieve function** — call `runtime.retrieve(query, top_k=...)`. Return or format `result.chunks`.
9. **Wire into an agent (if needed)** — expose `retrieve` as a `@rt.function_node` tool, or call it in a pre-invoke hook.
10. **Add a `if __name__ == "__main__":` block** — include both an ingest path and a query example so the user can run it immediately.

---

## Patterns to follow

### Minimal pipeline (in-memory, for demos/tests)
```python
import asyncio
from railtracks.retrieval import RetrievalRuntime
from railtracks.retrieval.loaders import TextLoader
from railtracks.retrieval.chunking import RecursiveCharacterChunker
from railtracks.retrieval.embedding import OpenAIEmbedding
from railtracks.retrieval.stores import VectorStore, InMemoryVectorBackend

async def main():
    runtime = RetrievalRuntime(
        chunker=RecursiveCharacterChunker(chunk_size=1000, overlap=200),
        embedder=OpenAIEmbedding(),
        store=VectorStore(InMemoryVectorBackend()),
        batch_size=100,
    )
    stats = await runtime.ingest_all(loader=TextLoader("data/my_file.txt"))
    print(f"chunks embedded: {stats.chunks_embedded}")

    result = await runtime.retrieve("your question here", top_k=5)
    for rc in result.chunks:
        print(f"[rank={rc.rank} score={rc.score:.3f}] {rc.chunk.content[:200]}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Persistent pipeline (Chroma, recommended for local dev)
```python
import asyncio
from railtracks.retrieval import RetrievalRuntime
from railtracks.retrieval.loaders import TextLoader
from railtracks.retrieval.chunking import RecursiveCharacterChunker
from railtracks.retrieval.embedding import OpenAIEmbedding
from railtracks.retrieval.stores import VectorStore, ChromaBackend

async def create_runtime() -> RetrievalRuntime:
    backend = await ChromaBackend.create(
        collection_name="my-collection",
        path="./my_db",
    )
    return RetrievalRuntime(
        chunker=RecursiveCharacterChunker(chunk_size=1000, overlap=200),
        embedder=OpenAIEmbedding(model="text-embedding-3-small"),
        store=VectorStore(backend),
        batch_size=100,
    )

async def main():
    runtime = await create_runtime()
    stats = await runtime.ingest_all(loader=TextLoader("data/my_file.txt"))
    print(f"loaded={stats.documents_loaded} chunks={stats.chunks_embedded} skipped={stats.documents_skipped}")

    result = await runtime.retrieve("your question here", top_k=5)
    for rc in result.chunks:
        print(f"[rank={rc.rank} score={rc.score:.3f}]\n{rc.chunk.content}\n")

if __name__ == "__main__":
    asyncio.run(main())
```

### Streaming ingestion events (for progress / error handling)
```python
from railtracks.retrieval import RetrievalRuntime
from railtracks.retrieval.runtime import BatchIngested, DocumentFailed, DocumentSkipped

async def ingest_with_progress(runtime: RetrievalRuntime, loader) -> None:
    async for event in runtime.ingest(loader=loader):
        if isinstance(event, BatchIngested):
            print(f"batch {event.batch}: {event.chunks_written} chunks written")
        elif isinstance(event, DocumentFailed):
            print(f"FAILED: {event.document_id} — {event.error}")
        elif isinstance(event, DocumentSkipped):
            print(f"skipped (unchanged): {event.document_id}")
```

### PDF ingestion
```python
from railtracks.retrieval.loaders import PyPDFLoader
from railtracks.retrieval.chunking import RecursiveCharacterChunker

# strategy="page" (default): one Document per page
# strategy="document": one Document for the whole PDF
loader = PyPDFLoader("data/report.pdf", strategy="page")
chunker = RecursiveCharacterChunker(chunk_size=800, overlap=100)
```

### CSV / structured data ingestion
```python
from railtracks.retrieval.loaders import CSVLoader

# content_col: the column whose text gets embedded
# metadata_cols: columns stored as metadata for filtering
loader = CSVLoader(
    file_path="data/products.csv",
    content_col="description",
    metadata_cols=["product_id", "category", "price"],
)
```

### HuggingFace dataset ingestion
```python
from railtracks.retrieval.loaders import HuggingFaceDatasetLoader

loader = HuggingFaceDatasetLoader(
    dataset_name="squad",
    split="train",
    text_column="context",
)
```

### Multi-tenancy with StoreScope
```python
from railtracks.retrieval.stores import StoreScope

user_scope = StoreScope(labels={"user_id": "u123", "org_id": "acme"})

# Write: ingest only into this scope
stats = await runtime.ingest_all(loader=loader, scope=user_scope)

# Read: retrieve only from this scope
result = await runtime.retrieve("question", top_k=5, scope=user_scope)

# Delete all documents for this scope
await runtime.store.clear(user_scope)
```

### RAG as an agent tool
```python
import railtracks as rt
from railtracks.retrieval import RetrievalRuntime

runtime: RetrievalRuntime = ...  # constructed at startup

@rt.function_node
async def search_knowledge_base(query: str) -> str:
    """Search the knowledge base for relevant context.
    Args:
        query: The natural language question to look up.
    Returns:
        Relevant excerpts from the knowledge base, ranked by similarity.
    """
    result = await runtime.retrieve(query, top_k=5)
    if not result.chunks:
        return "No relevant documents found."
    return "\n\n---\n\n".join(
        f"[score={rc.score:.3f}]\n{rc.chunk.content}"
        for rc in result.chunks
    )

RagAgent = rt.agent_node(
    "RAG Agent",
    tool_nodes=[search_knowledge_base],
    llm=rt.llm.AnthropicLLM("claude-sonnet-4-6"),
    system_message="You are a helpful assistant. Always search the knowledge base before answering.",
)
flow = rt.Flow(name="RAG Flow", entry_point=RagAgent)
```

### Sentence chunking (narrative / long-form text)
```python
from railtracks.retrieval.chunking import SentenceChunker

# chunk_size: number of sentences per chunk
# overlap: number of sentences shared between consecutive chunks
chunker = SentenceChunker(chunk_size=6, overlap=1)
```

### Local/offline embeddings with Ollama
```python
from railtracks.retrieval.embedding import OllamaEmbedding

embedder = OllamaEmbedding(model="nomic-embed-text", base_url="http://localhost:11434")
```

### Delete a document from the store
```python
# Re-ingest will upsert (content-hash skips unchanged docs)
# To explicitly remove:
await runtime.delete_document(document_id="doc-uuid-here")
```

---

## Things to avoid
- Don't call `ChromaBackend(...)` without `await backend.initialize()` — use `await ChromaBackend.create(...)` as the factory instead, it handles initialization.
- Don't mix embedding models across ingest and retrieve calls on the same collection — railtracks raises `EmbeddingModelMismatchError` to prevent silent vector corruption.
- Don't buffer the entire corpus in memory before ingesting — use `ingest_all()` with a loader that streams (`astream()`); never call `loader.aload()` manually and pass the list directly.
- Don't skip `documents_failed` in ingestion stats — always check and surface failures to the user.
- Don't use `InMemoryVectorBackend` in production — vectors are lost on process restart; use `ChromaBackend` with a `path` or `PgvectorBackend`.
- Don't construct `RetrievalRuntime` inside a request handler on every call — build it once at startup and reuse it.
- Don't pass raw document text directly to `retrieve()` as a query — `retrieve()` takes the user's natural language question, not a chunk.
