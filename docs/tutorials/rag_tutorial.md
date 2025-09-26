# 🔍 Tutorial: Using Retrieval-Augmented Generation (RAG)

This tutorial will get you from zero to RAG-powered agent in just a few minutes. We'll cover how Railtracks can help you build the perfect RAG Agent for your needs.

!!! tip "Don't know what RAG is or why you might want to use it? Check out our brief explainer [here](../background/RAG.md)"


When you create a RAG node, Railtracks automatically take care of chunking, embedding, and searching for you making it easy to use. All you need to do is provide a text file and let Railtracks take care of it for you from there. Let's look at an example of what this could look like.

## 🚀 Quickstart: Prebuilt RAG Node (Recommended)

This is the easiest way to add RAG to your app. Let's build a simple knowledge base in under 10 lines of code:

```python
--8<-- "docs/scripts/rag_examples.py:simple_rag_example"
```

!!! example "Example Output"
    Your RAG node can now answer questions based on your documents:

    Query: `"Who is Steve?"`

    Response: `"In our company, Steve is the lead engineer and ..."`

### 🎛️ Key Parameters You'll Want to Tune

!!! tip "Parameter Guide" 
    - **`documents`**: List of raw text strings to process 
    - **`embed_model`**: Embedding model name (e.g., "text-embedding-3-small") 
    - **`token_count_model`**: Model used for token-aware chunking (affects chunk_size units) 
    - **`chunk_size`**: Approximate tokens per chunk 
    - **`chunk_overlap`**: Token overlap between chunks to preserve context across boundaries 
    - **`top_k`** (on query): How many chunks to retrieve for a question

### 📁 Working with Files

To use text files as your data source, read them first, then pass the content to `rag_node`:

```python
--8<-- "docs/scripts/rag_examples.py:rag_with_files"
```

!!! warning "File Format Requirements" 
    - Files must be UTF-8 text 
    - For PDFs or other binary formats, extract text first using appropriate libraries 
    - For large corpora or advanced storage (e.g., FAISS/Qdrant), consider building a custom node

## 🎯 What Happens Under the Hood?

When you call `rag_node(...)`, here's the magic that happens automatically:

### Automated RAG Pipeline
=== "📖 Document Ingestion"
    Reads your raw text strings.

=== "✂️ Chunking"
    Splits documents into chunks based on `chunk_size` and `chunk_overlap` using a token-aware strategy tied to `token_count_model`.

=== "🧠 Embeddings"
    Calls the embedding service to embed each chunk into vectors using `embed_model`.

=== "📚 Storage"
    Writes VectorRecords (vector + text + metadata) into the default vector store (in-memory for quick starts).

=== "🔍 Retrieval on Query"
    Embeds the query and performs a vector similarity search to get the `top_k` most relevant snippets.

=== "📝 Prompt Composition"
    You turn the retrieved snippets into a context string and pass it to your LLM.

!!! success "Zero Configuration Required"
    You don't need to manage these steps yourself with the prebuilt node—they're executed automatically with sensible defaults!

## 🎯 Suggestion for Best Results

### 🧩 Chunk Size and Overlap

- **Suggested Range**: 600–1200 tokens with 10–20% overlap
- **Size Trade-offs**
    - **Larger chunks** → More context but less precise retrieval
    - **Smaller chunks** → More precise but may fragment meaning

### 🧠 Embedding Model Selection

- **`"text-embedding-3-small"`** → Cost-effective default for most use cases 
- **Upgrade to stronger models** when dealing with nuanced queries or specialized domains

### 📊 Top-K Retrieval

- **Start with 3–5** for most applications 
- **Increase for fragmented content** or highly diverse corpora 
- **Monitor performance** to avoid retrieving too much irrelevant context

### 💾 Storage Options

- **Default**: In-memory store (perfect for development and testing) 
- **Production**: Consider persistent stores like FAISS/Qdrant for larger datasets 
- **Custom configuration**: Use `store_config` parameter for advanced setups

---

!!! success "Next Steps"
    Ready to build something more advanced? Check out:

    - [RAG Reference Documentation](../tools_mcp/RAG.md) for custom implementations
    - [Tools Documentation](../tools_mcp/tools/tools.md) for integrating RAG with other capabilities
    - [Advanced Usage Patterns](../advanced_usage/context.md) for complex workflows
