# 🔍 Retrieval-Augmented Generation (RAG)

_Version: 0.1.0_

Need your AI agents to access your company's knowledge base, docs, or any private data? RAG is your answer! It enables grounded answering by retrieving relevant snippets from your documents and composing them into LLM prompts.

RAG ingests documents, chunks them, embeds the chunks into vectors, stores those vectors, and retrieves the most relevant snippets at query time—all automatically handled for you.

---

## 🎯 Two Ways to Get Started

We offer **two approaches** to integrate RAG into your application:

!!! tip "Choose Your Adventure 🚀" 
    1. **🏃‍♀️ Quick & Easy**: Use the prebuilt `rag_node` for instant setup 
    2. **🔧 Full Control**: Build a custom RAG node using the `RAG` class for maximum flexibility

### 🚀 Option 1: Prebuilt RAG Node (Recommended)

Perfect for getting started quickly! Wrap your RAG index into a callable node so other nodes and LLMs can retrieve relevant context and compose prompts.

```python
--8<-- "docs/scripts/rag_examples.py:rag_with_llm"
```

**File Loading Made Easy**

The `rag_node` function accepts raw text content only. For file loading, read the files first:

```python
--8<-- "docs/scripts/rag_examples.py:rag_with_files"
```

### 🔧 Option 2: Custom RAG Node (Advanced)

For maximum control and customization, build your own RAG implementation:

```python
--8<-- "docs/scripts/rag_examples.py:custom_rag_node"
```

**Usage:**

```python
--8<-- "docs/scripts/rag_examples.py:custom_rag_usage"
```

!!! note "Pro Tips" 
    - The callable node accepts `query` and optional `top_k`. Pass `top_k` via `rt.call_sync(retriever, "q", top_k=5)` 
    - `SearchResult` can be converted to plain text using `.to_list_of_texts()` 
    - You can inspect the object for similarity scores and metadata

---

## 📚 API Reference

### 🚀 Prebuilt RAG Node

**Function Signature:**

```python
railtracks.prebuilt.rag_node(
    documents: List[str],
    embed_model: str = "text-embedding-3-small",
    token_count_model: str = "gpt-4o",
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> DynamicFunctionNode
```

**Parameters:**

- **`documents`**: List of raw text strings to process and index
- **`embed_model`**: Embedding model name (default: "text-embedding-3-small")
- **`token_count_model`**: Model for token counting during chunking (default: "gpt-4o")
- **`chunk_size`**: Approximate tokens per chunk (default: 1000)
- **`chunk_overlap`**: Token overlap between chunks (default: 200)

**Behavior:**

- Builds a RAG index from documents
- Calls `embed_all` once during construction
- Returns a `DynamicFunctionNode` that you can call with `(query: str, top_k: int = 1)` to obtain a `SearchResult`

### 🔧 RAG Core Class

**Module:** `railtracks.rag.rag_core.RAG`

**Constructor:**

```python
RAG(
    docs: List[str],
    embed_config: Optional[dict] = None,
    store_config: Optional[dict] = None,
    chunk_config: Optional[dict] = None
)
```

**Important Parameters:**

- **`docs`**: List of raw text strings to process
- **`embed_config`**: Embedding provider config, e.g., `{"model": "text-embedding-3-small"}`
- **`store_config`**: Vector store configuration (default is in-memory)
- **`chunk_config`**: `{"chunk_size": int, "chunk_overlap": int, "model": str}` where model is used for token-based chunking

**Methods:**

- **`embed_all() -> None`**

  - Chunks docs, embeds chunks, and writes VectorRecords into the vector store
  - **Must be called before search** if you build RAG manually

- **`search(query: str, top_k: int = 3) -> SearchResult`**
  - Embeds the query and returns the top_k most similar chunks

**Return Types:**

- **`SearchResult`**
  - Provides convenience helpers such as `.to_list_of_texts()` to extract the retrieved snippet texts
  - May expose similarity metadata per entry depending on vector store implementation

### 🔩 Supporting Components

**Under the Hood Components:**

- **TextChunkingService**

  - Strategy: token-based chunking (`chunk_by_token`)
  - Controlled by `chunk_config`: `chunk_size`, `chunk_overlap`, `model` (for token counting)

- **EmbeddingService**

  - Produces vector embeddings for lists of strings
  - Configure via `embed_config`

- **Vector Store**
  - Created via `create_store(**store_config)`
  - Default: in-memory store suitable for development and tests

---

## ⚙️ Configuration and Performance

### 🧩 Chunking Strategy

**Best Practices:**

- **`chunk_size`**: Number of tokens per chunk (approximate, based on `token_count_model`)
- **`chunk_overlap`**: Number of tokens to overlap between adjacent chunks
- **Sweet spot**: Start with 600-1200 tokens with 10-20% overlap

### 🧠 Embeddings

**Model Selection:**

- **`"text-embedding-3-small"`** is a good default for many use cases (balance of quality and cost)
- **Upgrade to stronger models** for nuanced or specialized domains
- Configure via `embed_config`

### 💾 Vector Store Options

**Storage Recommendations:**

- **In-memory by default** (perfect for development and tests)
- **For larger corpora**: Consider FAISS/Qdrant or other backends supported by `create_store`
- **Production**: Use persistent storage for better performance

### 📊 Top-k Retrieval

**Finding the Right Balance:**

- **Typical values**: 3–5 chunks
- **Increase** if your content is highly fragmented or diverse
- **Monitor token usage** - larger chunk sizes and higher `top_k` values increase memory and token consumption

---

## 🔗 Related Documentation

### 📖 Features & Concepts

- [Node Authoring & Orchestration](../system_internals/node.md)
- [Tool Usage Patterns](tools/tools.md)
- [Advanced Context Management](../advanced_usage/context.md)

### 🛠️ External Libraries

**Powered By:**

- **[LiteLLM](https://github.com/BerriAI/litellm)** - Embeddings and chat transport

**Optional Vector Store Backends:**

- **[FAISS](https://github.com/facebookresearch/faiss)** - Fast similarity search
- **[Qdrant](https://qdrant.tech)** - Vector database
