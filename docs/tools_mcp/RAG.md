<!-- Retrieval-Augmented Generation Feature Documentation -->

# Retrieval-Augmented Generation (RAG)

RAG, or Retrieval-Augmented Generation, adds first-class “grounded answering” capabilities to agents by allowing them to search and retrieve relevant information.

RAG ingests arbitrary documents, converts them into vector embeddings, stores the vectors, and injects the most relevant context snippets into downstream Large-Language-Model (LLM) prompts so that generated answers are both up-to-date and verifiable.

**Version:** 0.0.1

---

## 1. Functional Overview

The feature is organised around two task sets:

1. **Indexing Pipeline** – transform raw documents into a searchable vector store
2. **Retrieval-Augmented Generation** – enrich LLM requests with retrieved context and generate the final answer

### 1.1 Indexing Pipeline

Responsible for taking user-supplied corpora (strings, file paths, URLs, etc.) and building an efficient similarity index.

```python
from RAG.rag_core import RAG             # Component: [RAG Engine](../components/rag_engine.md)

paths = ["./docs/handbook.pdf", "./docs/faq.md"]
rag = RAG(
    paths,
    input_type="path",
    chunk_config={"chunk_size": 800, "chunk_overlap": 120},
    embed_config={"model": "text-embedding-3-small"},
)
rag.embed_all()                          # → chunks, embeds & writes to vector store

print(rag.vector_store.count())          # sanity-check
```

Key points

• Chunking strategy, embedding model and store backend are all **configurable** and can be in memory or database.
• The default `InMemoryVectorStore` is perfect for notebooks and unit tests; swap for FAISS/Pinecone by passing `store_config={"type": "faiss"}` once the corresponding backend exists.

### 1.2 Retrieval-Augmented Generation

Wraps the index in a Request-Completion `Node` so that other nodes or HTTP handlers can query the corpus and fuse the results into the prompt.

```python
from RAG.rag_node import get_rag_node    # Component: [RAG Engine](../components/rag_engine.md)
from requestcompletion.llm import MessageHistory, UserMessage
from nodes.library.terminal_llm import TerminalLLM   # Feature: [LLM](../features/llm.md)

# 1. Build the retrieval node (one-off)
retriever = get_rag_node(
    ["./docs/policies/*.txt"],
    embed_model="text-embedding-3-small",
)

# 2. Compose with an LLM node inside your graph
question   = "How do we handle user data?"
references = retriever(question)                     # top-k SearchResult[]
context    = "\n\n".join(r.record.text for r in references)

llm_node = TerminalLLM(
    model_name = "gpt-4o",
    prompt     = f"""
Answer the user question using the context below.
If the answer is not contained, say "I don't know".

Context:
{context}

Question:
{question}
"""
)
answer = await llm_node.tracked_invoke()
print(answer)
```

• `SearchResult` objects carry both the snippet text **and** the similarity score; keep the top-N or threshold as desired.  
• Nothing prevents building more sophisticated prompt-assemblers (e.g. citation tagging), but the above shows the minimum working example.

---

## 2. Related Files

### 2.1 Related Component Files

- [`components/rag_engine.md`](../components/rag_engine.md) – Implements the underlying index and search logic.
- [`components/llm_abstraction.md`](../components/llm_abstraction.md) – Supplies LLM chat/structured/streaming calls used during generation.
- [`components/node_framework.md`](../components/node_framework.md) – Execution substrate for nodes created by `get_rag_node`.
- [`components/logging_utilities.md`](../components/logging_utilities.md) – Structured logging for retrieval and generation phases.
- [`components/exception_framework.md`](../components/exception_framework.md) – Validation and error classes surfaced to callers.

### 2.2 Related Feature Files

- [`features/nodes.md`](../features/nodes.md) – Authoring & orchestration of nodes.
- [`features/llm.md`](../features/llm.md) – High-level usage patterns for the LLM feature (prompt-builder templates, tool-calling, etc.).

### 2.3 External Dependencies

- [`https://github.com/BerriAI/litellm`](https://github.com/BerriAI/litellm) – Embeddings and chat transport.
- Vector store backends (optional):
  - [`https://github.com/facebookresearch/faiss`](https://github.com/facebookresearch/faiss)
  - [`https://qdrant.tech`](https://qdrant.tech)

---
