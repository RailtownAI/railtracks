Beta

`railtracks.retrieval` is in beta. Please expect API changes between minor releases.

Migrated from older modules

`railtracks.rag` and `railtracks.vector_stores` are removed. Everything now lives under `railtracks.retrieval`.

This module is in a beta and we are actively polishing the pieces.

# Quickstart

`railtracks.retrieval` is the module for everything that turns raw sources into a searchable index and queries it back — **ingestion** (loading, chunking, embedding) and **vector search**, with the same runtime answering both.

`RetrievalRuntime` pipelines the four stages:

```
flowchart LR
    Sources["Sources  
(files, URLs, dirs)"]
    Loader{{"1. Loader"}}
    Chunker{{"2. Chunker"}}
    Embedder{{"3. Embedder"}}
    Store[("4. Store")]
    Query(["Query"])
    Results>"RetrievalResult"]

    Sources --> Loader
    Loader --> |Documents| Chunker
    Chunker --> |Chunks| Embedder
    Embedder --> |EmbeddedChunks| Store
    Query --> Embedder
    Store --> Results

    classDef source fill:#60A5FA,fill-opacity:0.3
    classDef process fill:#FBBF24,fill-opacity:0.3
    classDef store fill:#34D399,fill-opacity:0.3
    classDef output fill:#FECACA,fill-opacity:0.3

    class Sources,Query source;
    class Loader,Chunker,Embedder process;
    class Store store;
    class Results output;
```

______________________________________________________________________

## Minimal pipeline

```python
import asyncio

from railtracks.retrieval import RetrievalRuntime
from railtracks.retrieval.chunking import SentenceChunker
from railtracks.retrieval.embedding import OpenAIEmbedding
from railtracks.retrieval.loaders import TextLoader
from railtracks.retrieval.stores import InMemoryVectorBackend, VectorStore


async def main():
    runtime = RetrievalRuntime(
        chunker=SentenceChunker(chunk_size=7, overlap=2),
        embedder=OpenAIEmbedding(model="text-embedding-3-small"),
        store=VectorStore(InMemoryVectorBackend()),
        batch_size=16,  # smaller batch size for faster embedding in this example
    )

    stats = await runtime.ingest_all(loader=TextLoader("./docs"))
    print(f"ingested {stats.documents_loaded} docs / {stats.chunks_embedded} chunks")

    result = await runtime.retrieve("how do I configure observability?", top_k=5)
    for hit in result.chunks:
        print(f"  [{hit.score:.3f}] {hit.chunk.content}")


asyncio.run(main())
```

Three options decide the shape of a runtime: **chunker**, **embedder**, **store**. **Loader** is a parameter passed to `.ingest(...)` or `.ingest_all(...)` allowing reading of file systems with different file types.

______________________________________________________________________

## Where to go next

| You want to…                                                                                                | Read                                                                                        |
| ----------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| Get documents into the store (streaming events, re-ingest, multi-tenant writes, sanitization, token guards) | **[Ingestion](https://docs.railtracks.org/retrieval/runtime/ingestion/index.md)**           |
| Run vector search (top-k, metadata filters, per-call scope) or attach a runtime to an agent                 | **[Retrieval](https://docs.railtracks.org/retrieval/runtime/retrieval/index.md)**           |
| Understand the internals, async model, and to customize things                                              | **[Components → Design](https://docs.railtracks.org/retrieval/components/design/index.md)** |

______________________________________________________________________

## Key types

The following data models flow through the pipeline. Each links to the page that owns its full description.

| Type                                                                                                              | What it is                                                                                                                                             |
| ----------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| [`Document`](https://docs.railtracks.org/retrieval/components/ingestion/base/#the-document-object)                | One unit of source content produced by a loader.                                                                                                       |
| [`Chunk`](https://docs.railtracks.org/retrieval/components/chunking/base/#the-chunk-object)                       | A slice of a Document produced by a chunker carrying `document_id` and metadata.                                                                       |
| [`EmbeddedChunk`](https://docs.railtracks.org/retrieval/components/embeddings/overview/#the-embeddedchunk-object) | A chunk plus its embedding vector and model name.                                                                                                      |
| [`StoreEntry`](https://docs.railtracks.org/retrieval/components/stores/base/#data-models)                         | The atomic unit a store reads and writes.                                                                                                              |
| [`RetrievalResult`](https://docs.railtracks.org/retrieval/runtime/retrieval/index.md)                             | What `runtime.retrieve()` returns: ranked `RetrievedChunk`s plus the query.                                                                            |
| [`StoreScope`](https://docs.railtracks.org/retrieval/components/stores/base/#data-models)                         | A hard-filter namespace: a label dict (`{"user_id": "alice"}`, `{"organization": "acme"}`, etc.) enforced as equality filters on every read and write. |

______________________________________________________________________

## Stage choices

Pick the right component for each stage. Each link goes to the page that covers the trade-offs.

| Stage     | Built-in options                                                                                                               | Picked by                                                                                          |
| --------- | ------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- |
| **Load**  | `TextLoader`, `CSVLoader`, `PyPDFLoader`, `PyPDFOCRLoader`, `HuggingFaceDatasetLoader`, `JSONLoader`, `LangChainLoaderAdapter` | [Ingestion overview](https://docs.railtracks.org/retrieval/components/ingestion/base/index.md)     |
| **Chunk** | `RecursiveCharacterChunker`, `MarkdownHeaderChunker`, `SentenceChunker`, `FixedTokenChunker`                                   | [Chunking methods](https://docs.railtracks.org/retrieval/components/chunking/methods/index.md)     |
| **Embed** | `OpenAIEmbedding`, `AzureEmbedding`, `OllamaEmbedding`, `LiteLLMEmbedding`                                                     | [Embeddings methods](https://docs.railtracks.org/retrieval/components/embeddings/methods/index.md) |
| **Store** | `VectorStore` with `InMemoryVectorBackend`, `ChromaBackend`, or `PgvectorBackend`                                              | [Store backends](https://docs.railtracks.org/retrieval/components/stores/backends/index.md)        |
