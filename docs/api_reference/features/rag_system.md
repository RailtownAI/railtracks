<!--
Feature documentation for the Retrieval-Augmented Generation (RAG) system.
Remove comment blocks once you’re confident the document is complete.
-->

# RAG System

Provides a plug-and-play Retrieval-Augmented Generation pipeline for chunking, embedding, storing, and semantically searching large collections of documents.

**Version:** 0.0.1 <!-- bump on any externally-observable change -->

## Table of Contents

- [1. Functional Overview](#1-functional-overview)
- [2. External Contracts](#2-external-contracts)
- [3. Design and Architecture](#3-design-and-architecture)
- [4. Related Files](#4-related-files)
- [CHANGELOG](#changelog)

---

## 1. Functional Overview

The RAG System feature bundles several lower-level components into a cohesive workflow that:

1.  Ingests raw text or files.
2.  Splits the text into overlapping chunks.
3.  Generates dense embeddings for every chunk.
4.  Stores the embeddings (and rich metadata) in a vector store.
5.  Performs similarity search to retrieve the *k* most relevant chunks for an arbitrary user query.

The end result is a simple API that lets application developers add “chat-with-my-data” or “semantic search” capabilities without worrying about the details of chunk sizes, embedding models, or vector-store plumbing.

### 1.1 Quickstart (all-in-one helper)

The `railtracks.prebuilt.rag_node.rag_node` helper wraps the entire flow in a single **function node** that can be mounted inside a RailTracks graph.

```python
from railtracks.prebuilt.rag_node import rag_node

documents = [
    "The mitochondrion is the powerhouse of the cell.",
    "ATP is synthesized via oxidative phosphorylation.",
]

search_node = rag_node(
    documents,
    embed_model="text-embedding-3-small",
    token_count_model="gpt-4o",
    chunk_size=1_000,
    chunk_overlap=200,
)

print(search_node("What produces ATP?")[0].record.text)
# ➜ "ATP is synthesized via oxidative phosphorylation."
```

Internally this helper:

1. Creates a `rag.rag_core.RAG` instance.  
2. Calls `embed_all()` to preprocess and index the documents.  
3. Returns a callable node that runs `RAG.search()` for every invocation.

### 1.2 Fine-grained Control

If you need to swap out the vector store, change similarity metrics, or stream documents gradually, use `rag.rag_core.RAG` directly.

```python
from railtracks.rag.rag_core import RAG

rag = RAG(
    docs=["some text", "…"],
    embed_config={"model": "text-embedding-3-small"},
    store_config={"backend": "memory", "metric": "cosine"},
    chunk_config={"chunk_size": 1500, "chunk_overlap": 300, "model": "gpt-3.5-turbo"},
)

rag.embed_all()                               # ⬅️ ingest + index
hits = rag.search("semantic query", top_k=5)  # ⬅️ retrieve
for hit in hits:
    print(hit.score, hit.record.text)
```

### 1.3 Incremental Updates

`RAG` exposes the underlying `vector_store` so you can add new `VectorRecord`s or delete outdated ones without rebuilding the entire index:

```python
new_id = rag.vector_store.add(
    ["fresh note about ATP"],
    embed=True,
    metadata=[{"source": "notes.md"}],
)[0]

rag.vector_store.delete([new_id])
```

## 2. External Contracts

The RAG System is a purely in-process Python feature and does **not** expose HTTP endpoints or CLI commands. The only external contract is the requirement for an embedding provider that follows the `litellm` interface.

### 2.1 Environment Variables

| Name              | Purpose                                               | Default |
| ----------------- | ----------------------------------------------------- | ------- |
| `OPENAI_API_KEY`  | Used by `EmbeddingService` when no `api_key` passed.  | _None_  |

### 2.2 Configuration Objects

All tunables are passed in as **plain Python dictionaries**:

* **`embed_config`** → forwarded to `components/embedding_service.md`  
* **`chunk_config`** → forwarded to `components/chunking_service.md`  
* **`store_config`** → forwarded to `components/vector_store_factory.md`

## 3. Design and Architecture

At a high-level the feature implements the canonical RAG pipeline:

```mermaid
flowchart LR
    A[Raw Docs / Paths] -->|Text| B[TextChunkingService]
    B -->|Chunks| C[EmbeddingService]
    C -->|Vectors\n+ Metadata| D[VectorStore (In-Memory)]
    E[Query] -->|Embed| C
    C -->|Query Vector| F[Similarity Search]
    F -->|Top-k SearchResult| G[Caller / LLM]
```

### 3.1 Component Boundaries

| Stage               | Component (doc)                                        | Responsibility                                                             |
| ------------------- | ------------------------------------------------------ | -------------------------------------------------------------------------- |
| Chunking            | `components/chunking_service.md`                       | Overlapping splits by char/token.                                          |
| Embedding           | `components/embedding_service.md`                      | Batch requests to `litellm.embedding`.                                     |
| Storage + Search    | `components/vector_store_base.md`  ← factory / memory  | CRUD, similarity search, persistence.                                      |
| Data Abstraction    | `components/text_object_management.md`                 | Holds raw content, chunk list, embeddings, metadata hash.                  |
| Utilities           | `components/rag_utilities.md`, `components/vector_store_utilities.md` | Token counting, file-ops, vector math, stable hashing, UUIDs.              |
| Orchestration       | `components/rag_core.md`                               | Glue code that wires every sub-component into a single façade.             |
| Pre-built Node      | `components/rag_node.md`                               | Exposes a single RailTracks node for graph composition.                    |

### 3.2 Key Design Decisions & Trade-offs

1. **In-memory first:**  
   The default backend is `InMemoryVectorStore` for zero-dependency prototyping. Disk persistence is provided via simple pickle-based `persist()` / `load()`. A future roadmap item (v0.1) is to add FAISS / Qdrant backends via the factory.

2. **Overlapping chunks:**  
   A default `chunk_overlap` of 20 % (200 tokens for a 1 000 token chunk) was chosen to reduce boundary information loss at the cost of minor duplication in the store.

3. **Cosine similarity + normalization:**  
   Normalization is automatically turned on when the metric is `cosine`, ensuring distance computations remain numerically stable and comparable.

4. **Loose coupling via factory functions:**  
   Both the vector store and chunking strategy can be swapped by injecting a different `backend` or `strategy` callable respectively—no changes needed in `RAG`.

5. **Batch-size-agnostic embeddings:**  
   `EmbeddingService.embed()` internally chunks long input lists into 8-item batches to stay within OpenAI’s recommended payload sizes, but keeps the public signature simple.

### 3.3 Rejected Alternatives

- **Rigid pipeline class**: An earlier design hard-coded the ingestion order inside a monolithic class. This was replaced by the current thin façade + injectable services to encourage experimentation (e.g., multi-modal embeddings).  
- **Auto-token-chunking via GPT-4**: Considered using GPT-4 to dynamically decide split points (`chunk_smart`). Ultimately postponed due to latency/cost concerns; placeholder method remains for future work.

## 4. Related Files

### 4.1 Related Component Files

- [`components/rag_node.md`](../components/rag_node.md): one-line RailTracks node wrapper around `RAG`.
- [`components/rag_core.md`](../components/rag_core.md): orchestrator that drives chunking, embedding, storage, and search.
- [`components/chunking_service.md`](../components/chunking_service.md): text splitting strategies.
- [`components/embedding_service.md`](../components/embedding_service.md): litellm embedding interface.
- [`components/vector_store_base.md`](../components/vector_store_base.md): abstract CRUD + search API for any vector store backend.
- [`components/vector_store_factory.md`](../components/vector_store_factory.md): factory that selects `InMemoryVectorStore` by default.
- [`components/in_memory_vector_store.md`](../components/in_memory_vector_store.md): default, dependency-free backend.
- [`components/text_object_management.md`](../components/text_object_management.md): canonical representation of a document + metadata.
- [`components/rag_utilities.md`](../components/rag_utilities.md): tokenization & file helpers.
- [`components/vector_store_utilities.md`](../components/vector_store_utilities.md): vector math, UUID, hashing.

### 4.2 External Dependencies

- [`https://github.com/BerriAI/litellm`](https://github.com/BerriAI/litellm): lightweight wrapper used for both embeddings and tokenization.
- [`https://pypi.org/project/tiktoken/`](https://pypi.org/project/tiktoken/): fast tokenizer leveraged by `LORAGTokenizer`.

---

## CHANGELOG

- **v0.0.1** (2024-06-07) [`<INIT>`]: Initial specification of the RAG System feature.