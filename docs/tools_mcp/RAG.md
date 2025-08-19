
<!-- Retrieval-Augmented Generation Feature Documentation -->

# Retrieval-Augmented Generation (RAG)

RAG enables grounded answering by retrieving relevant snippets from your documents and composing them into LLM prompts.

RAG ingests documents, chunks them, embeds the chunks into vectors, stores those vectors, and retrieves the most relevant snippets at query time.

Version: 0.0.2

---

## 1. Functional Overview

We offer two appraoch of intergrating RAG into your application:
1. Using the prebuilt `rag_node` for quick setup.
2. Building a custom RAG node using the `RAG` class for more control and flexibility.

### 1.1 Retrieval-Augmented Generation

Wrap the RAG index into a callable node so other nodes and LLMs can retrieve relevant context and compose prompts.

**Prebuilt node (simplified):**

```python
import railtracks as rt
from railtracks.prebuilt import rag_node
from railtracks.nodes.concrete import TerminalLLM
from railtracks.llm import OpenAILLM

# Build the retrieval node once
retriever = rag_node(
    ["./docs/faq.txt", "./docs/policies.txt"],  # or raw strings with input_type="text"
    input_type="path",
    embed_model="text-embedding-3-small",
    # token_count_model="gpt-4o",
    # chunk_size=1000,
    # chunk_overlap=200,
)

# Retrieve context
question = "How do we handle user data?"
search_result = rt.call_sync(retriever, question, top_k=3)
context = "\n\n".join(search_result.to_list_of_texts())

# You might include RAG result in an LLM prompt
llm_node = TerminalLLM(
    llm_model=OpenAILLM("gpt-4o"),
    user_input=f"""
Answer the user question using the context below.
If the answer is not contained, say "I don't know".

Context:
{context}

Question:
{question}
""",
)
```

### 1.2 Custom RAG Node

```python
from typing import Type
import railtracks as rt
from railtracks.nodes.concrete import DynamicFunctionNode
from railtracks.rag.rag_core import RAG, SearchResult

def rag_node(
    documents: list,
    input_type: str = "text",              # 'text' or 'path'
    embed_model="text-embedding-3-small",
    token_count_model="gpt-4o",
    chunk_size=1000,
    chunk_overlap=200,
) -> Type[DynamicFunctionNode]:
    """
    Creates a RAG node that supports vector search over the provided documents.
    """

    rag_core = RAG(
        docs=documents,
        embed_config={"model": embed_model},
        store_config={},
        chunk_config={
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "model": token_count_model,
        },
        input_type=input_type,
    )
    rag_core.embed_all()

    def query(query: str, top_k: int = 1) -> SearchResult:
        return rag_core.search(query, top_k=top_k)

    return rt.function_node(query)

# Usage
retriever = rag_node(["Alpha loves apples", "Beta loves bananas"], input_type="text")
res = rt.call_sync(retriever, "Who loves apples?", top_k=3).to_list_of_texts()
```

Notes:
- The callable node accepts `query` and optional `top_k`. Pass `top_k` via `rt.call_sync(retriever, "q", top_k=5)`.
- `SearchResult` can be converted to plain text using `.to_list_of_texts()`. You can inspect the object for similarity scores and metadata.

---

## 2. API Reference

### 2.1 Prebuilt RAG Node

**Signature:**
- `railtracks.prebuilt.rag_node( documents: list, input_type: str = "text", embed_model: str = "text-embedding-3-small", token_count_model: str = "gpt-4o", chunk_size: int = 1000, chunk_overlap: int = 200 ) -> DynamicFunctionNode`

**Behavior:**
- Builds a RAG index from documents.
- Calls `embed_all` once during construction.
- Returns a `DynamicFunctionNode` that you can call with `(query: str, top_k: int = 1)` to obtain a `SearchResult`.

### 2.2 RAG Core Class

**Module:**
- `railtracks.rag.rag_core.RAG`

**Constructor:**
- `RAG( docs: List[Any], embed_config: Optional[dict] = None, store_config: Optional[dict] = None, chunk_config: Optional[dict] = None, input_type: str = "text"  # 'text' or 'path' )`

**Important args:**
- `docs`: list of raw strings (`input_type="text"`) or file paths (`input_type="path"`).
- `embed_config`: embedding provider config, e.g., `{"model": "text-embedding-3-small"}`.
- `store_config`: vector store configuration (default is in-memory).
- `chunk_config`: `{"chunk_size": int, "chunk_overlap": int, "model": str}`, where model is used for token-based chunking.
- `input_type`: `"text"` or `"path"` (`path` expects UTF-8 text files).

**Methods:**
- `embed_all() -> None`
  - Chunks docs, embeds chunks, and writes VectorRecords into the vector store.
  - Must be called before search if you build RAG manually.
- `search(query: str, top_k: int = 3) -> SearchResult`
  - Embeds the query and returns the top_k most similar chunks.

**Return Types:**
- `SearchResult`
  - Provides convenience helpers such as `.to_list_of_texts()` to extract the retrieved snippet texts.
  - May expose similarity metadata per entry depending on vector store implementation.

### 2.3 Supporting Components

- **TextChunkingService**
  - Strategy: token-based chunking (`chunk_by_token`).
  - Controlled by `chunk_config`: `chunk_size`, `chunk_overlap`, `model` (for token counting).
- **EmbeddingService**
  - Produces vector embeddings for lists of strings. Configure via `embed_config`.
- **Vector Store**
  - Created via `create_store(**store_config)`.
  - Default: in-memory store suitable for development and tests.

---

## 3. Configuration and Performance

- **Chunking**
  - `chunk_size`: number of tokens per chunk (approximate, based on `token_count_model`).
  - `chunk_overlap`: number of tokens to overlap between adjacent chunks.
- **Embeddings**
  - Choose a model that balances quality and cost. `"text-embedding-3-small"` is a good default for many use cases.
- **Vector Store**
  - In-memory by default. For larger corpora, consider FAISS/Qdrant or other backends supported by `create_store`.
- **Top-k Retrieval**
  - Typical values are 3–5. Increase if your content is highly fragmented or diverse.
- **Resource Considerations**
  - Larger chunk sizes and higher `top_k` values increase memory and token usage.

---

## 4. Related Files

### 4.1 Related Feature Files

- **nodes.md**  
  – Authoring & orchestration of nodes.

- **llm.md**  
  – High-level usage patterns for the LLM feature (prompt-builder templates, tool-calling, etc.).

### 4.2 Related Library Files

- [https://github.com/BerriAI/litellm](https://github.com/BerriAI/litellm)  
  – Embeddings and chat transport.

- **Vector store backends (optional):**  
  - [https://github.com/facebookresearch/faiss](https://github.com/facebookresearch/faiss)  
  - [https://qdrant.tech](https://qdrant.tech)