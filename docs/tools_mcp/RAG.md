# Retrieval-Augmented Generation (RAG)

Need your AI agents to access your company's knowledge base, docs, or any private data? RAG is your answer! It enables grounded answering by retrieving relevant snippets from your documents and composing them into LLM prompts.

RAG ingests documents, chunks them, embeds the chunks into vectors, stores those vectors, and retrieves the most relevant snippets at query time—all automatically handled for you.

---

## Two Ways to Get Started

We offer **two approaches** to integrate RAG into your application:

!!! tip "Choose Your Adventure" 
    1. **Quick & Easy**: Use the prebuilt `rag_node` for instant setup 
    2. **Full Control**: Build a custom RAG node using the `RAG` class for maximum flexibility

### Option 1: Prebuilt RAG Node (Recommended)

Perfect for getting started quickly! Wrap your RAG index into a callable node so other nodes and LLMs can retrieve relevant context and compose prompts.

```python
--8<-- "docs/scripts/rag_examples.py:rag_with_llm"
```

**File Loading Made Easy**

The `rag_node` function accepts raw text content only. For file loading, read the files first:

```python
--8<-- "docs/scripts/rag_examples.py:rag_with_files"
```

### Option 2: Custom RAG Node (Advanced)

For maximum control and customization, build your own RAG node.

```python
--8<-- "docs/scripts/rag_examples.py:custom_rag_node"
```


!!! note "Pro Tips" 
    - The callable node accepts `query` and optional `top_k` to control number of retrieved chunks. 
    - `SearchResult` can be converted to plain text using `.to_list_of_texts()` 
    - You can inspect the object for similarity scores and metadata



### Chunking Strategy

**Best Practices:**

- **`chunk_size`**: Number of tokens per chunk (approximate, based on `token_count_model`)
- **`chunk_overlap`**: Number of tokens to overlap between adjacent chunks
- **Sweet spot**: Start with 600-1200 tokens with 10-20% overlap

### Embeddings

**Model Selection:**

- **`"text-embedding-3-small"`** is a good default for many use cases (balance of quality and cost)
- **Upgrade to stronger models** for nuanced or specialized domains
- Configure via `embed_config`

### Vector Store Options

**Storage Recommendations:**

- **In-memory by default** (perfect for development and tests)
- **For larger corpora**: Consider FAISS/Qdrant or other backends supported by `create_store`
- **Production**: Use persistent storage for better performance

### Top-k Retrieval

**Finding the Right Balance:**

- **Typical values**: 3–5 chunks
- **Increase** if your content is highly fragmented or diverse
- **Monitor token usage** - larger chunk sizes and higher `top_k` values increase memory and token consumption

---

## Related Documentation

### Features & Concepts

- [Tool Usage Patterns](tools/tools.md)
- [Advanced Context Management](../advanced_usage/context.md)

### External Libraries

**Powered By:**

- **[LiteLLM](https://github.com/BerriAI/litellm)** - Embeddings and chat transport

**Optional Vector Store Backends:**

- **[FAISS](https://github.com/facebookresearch/faiss)** - Fast similarity search
- **[Qdrant](https://qdrant.tech)** - Vector database
