# Build a Railtracks RAG Pipeline

The user wants to build a retrieval-augmented generation (RAG) pipeline using railtracks: $ARGUMENTS

## How railtracks retrieval works
- **Loaders** read source documents (files, PDFs, CSVs, cloud storage, databases) and yield `Document` objects.
- **Chunkers** split each document into smaller overlapping `Chunk` objects that fit inside an embedding window.
- **Embedders** convert chunks (and later, queries) into dense vectors.
- **Stores** persist chunks with their vectors and support nearest-neighbour lookup.
- **`RetrievalRuntime`** wires loader → chunker → embedder → store into `ingest_all()` and `retrieve()` calls.

### Loader Selection
| Source | Class | Key params |
|---|---|---|
| `.txt` / `.md` file | `TextLoader` | `file_path` |
| PDF | `PyPDFLoader` | `file_path`, `breakdown_strategy="page"\|"document"` |
| PDF + OCR fallback | `PyPDFOCRLoader` | `file_path`, `force_ocr=False` |
| CSV | `CSVLoader` | `file_path`, `content_columns`, `ignore_columns` |
| JSON | `JSONLoader` | `file_path`, `content_keys="*"` |
| AWS S3 | `S3Loader` | `bucket`, `prefix`, `keys` |
| SQL database | `SQLLoader` | `connection_string`, `table_or_query`, `content_column` |

### Chunker Selection
| Use case | Class | Key params |
|---|---|---|
| General prose (recommended default) | `RecursiveCharacterChunker` | `chunk_size=1000`, `overlap=200` |
| Sentence-boundary aware | `SentenceChunker` | `chunk_size=5` (sentences), `overlap=1` |
| Token-precise | `FixedTokenChunker` | `chunk_size=400`, `overlap=200` |
| Markdown / structured docs | `MarkdownHeaderChunker` | `chunk_size=1000` |
| Semantic topic boundaries | `SemanticChunker` | `embedder=<same embedder>`, `threshold_percentile=95.0` |

### Embedder Selection
| Provider | Class | Key params |
|---|---|---|
| OpenAI | `OpenAIEmbedding` | `model="text-embedding-3-small"`, `dimensions` |
| Azure OpenAI | `AzureEmbedding` | `deployment`, `api_base`, `api_version` |
| Ollama (local) | `OllamaEmbedding` | `model="nomic-embed-text"`, `api_base` |
| Any LiteLLM provider | `LiteLLMEmbedding` | `model="provider/model-name"` |

### Vector Store / Backend Selection
| Backend | Class | When to use |
|---|---|---|
| Local disk (development) | `ChromaBackend(path="./db")` | No infra needed, persists between runs |
| In-process ephemeral | `ChromaBackend()` | Testing / one-shot scripts |
| Remote Chroma server | `ChromaBackend(host=..., port=...)` | Shared/production Chroma |
| PostgreSQL + pgvector | `PgvectorBackend(dsn=...)` | Production, existing Postgres |
| In-memory with snapshot | `InMemoryBackend(snapshot_path=...)` | Lightweight local dev |

---

## Steps
1. **Read the existing code** — check what files already exist in the project before writing anything.
2. **Choose your components** — pick a loader, chunker, embedder, and backend from the tables above. Ask the user to clarify if the source format or provider is not obvious from `$ARGUMENTS`.
3. **Create the runtime** — instantiate `ChromaBackend` (or another backend) with `await Backend.create(...)`, wrap it in `VectorStore`, and pass both with the chunker and embedder to `RetrievalRuntime`.
4. **Ingest documents** — call `await runtime.ingest_all(loader=...)`. Print `stats.documents_loaded`, `stats.chunks_embedded`, and `stats.documents_skipped` so the user can confirm it worked.
5. **Retrieve** — call `await runtime.retrieve(query=..., top_k=5)`. The result is a `RetrievalResult`; the matched text lives in `result.chunks[i].chunk.content`.
6. **Wire into an agent (optional)** — if the user wants an LLM to answer questions, wrap `retrieve` in a `@rt.function_node` tool and pass it to `rt.agent_node()`.
7. **Add invocation code** — include a `if __name__ == "__main__":` block with `asyncio.run(...)` calls for both ingestion and retrieval so the user can run it immediately.
8. **Check imports** — all retrieval classes live under `railtracks.retrieval` and its sub-modules. Import `asyncio` for `asyncio.run()`.

---

## Patterns to Follow

### Runtime Setup
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
        path="./my_db/"         # omit for ephemeral in-memory
    )
    return RetrievalRuntime(
        chunker=RecursiveCharacterChunker(chunk_size=1000, overlap=200),
        embedder=OpenAIEmbedding(),
        store=VectorStore(backend=backend),
        batch_size=64,
    )
```

### Ingestion
```python
async def ingest(runtime: RetrievalRuntime) -> None:
    stats = await runtime.ingest_all(
        loader=TextLoader("data/my-file.txt")
    )
    print(
        f"loaded={stats.documents_loaded} "
        f"chunks={stats.chunks_embedded} "
        f"skipped={stats.documents_skipped}"
    )
```

### Retrieval
```python
async def retrieve(runtime: RetrievalRuntime, query: str, top_k: int = 5) -> list[str]:
    result = await runtime.retrieve(query=query, top_k=top_k)
    return [rc.chunk.content for rc in result.chunks]
```

### RAG Agent (retrieval as a tool)
```python
import railtracks as rt

# Build runtime once at module level (shared across calls)
_runtime: RetrievalRuntime | None = None

@rt.function_node
async def search_documents(query: str) -> str:
    """Search the document store and return relevant text passages.
    Args:
        query: The question or topic to look up.
    Returns:
        Relevant passages joined by newlines.
    """
    result = await _runtime.retrieve(query=query, top_k=5)
    return "\n---\n".join(rc.chunk.content for rc in result.chunks)

RAGAgent = rt.agent_node(
    "RAG Agent",
    tool_nodes=[search_documents],
    llm=rt.llm.AnthropicLLM("claude-sonnet-4-6"),
    system_message=(
        "You are a helpful assistant. Use the search_documents tool to look up "
        "information before answering. Always ground your answer in retrieved passages."
    ),
)
flow = rt.Flow(name="RAG Flow", entry_point=RAGAgent)

if __name__ == "__main__":
    async def main():
        global _runtime
        _runtime = await create_runtime()
        # Ingest once, then query
        await ingest(_runtime)
        result = flow.invoke("Your question here")
        print(result)
    asyncio.run(main())
```

### Streaming Ingestion Events
```python
async def ingest_streaming(runtime: RetrievalRuntime) -> None:
    async for event in runtime.ingest(loader=TextLoader("data/large-file.txt")):
        print(event)   # BatchIngested | EmbeddingFailure | DocumentFailed | DocumentSkipped
```

### Multiple Queries
```python
async def ask_many(runtime: RetrievalRuntime, queries: list[str], top_k: int = 5):
    return [
        await runtime.retrieve(query=q, top_k=top_k)
        for q in queries
    ]
```

---

## Things to Avoid
- Don't re-create `RetrievalRuntime` on every query — instantiate it once and reuse it.
- Don't skip `await Backend.create(...)` — backends are async-initialized; constructing them directly without `create()` leaves them unready.
- Don't ignore `stats.documents_skipped` — skipped documents usually mean duplicate IDs; the store de-dupes by content hash so re-running ingestion is safe.
- Don't use `SemanticChunker` with a different embedder than the one used for retrieval — the vector spaces must match.
- Don't hardcode the collection name across ingest and retrieve calls — put it in one place so they stay in sync.
