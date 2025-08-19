# Tutorial: Using Retrieval-Augmented Generation (RAG)

Version: 0.0.2

Welcome to the tutorial on using RAG to ground your LLM applications in your own data. This guide explains why and when to use RAG, what happens under the hood, and how to get started quickly with the prebuilt node. You’ll also find practical tips for quality and performance.

## Why RAG?

LLMs are powerful, but they:
- Don’t know your private or proprietary data.
- Can go out of date as facts change.
- Sometimes hallucinate.

RAG fixes this by retrieving relevant snippets from your documents and injecting them into the prompt so the model answers using real, current context.

Use RAG when:
- You need answers grounded in internal docs, policies, FAQs, knowledge bases, logs.
- Your knowledge changes frequently and must be reflected immediately.
- You want traceability and the ability to show the exact source passages.
- Your prompts would exceed token limits without selective retrieval.

RAG may be overkill when:
- You only need general world knowledge that your base model already knows.
- Your corpus is tiny and always fully fits into the prompt.

## How RAG works (at a glance)

When you construct a RAG node, the system performs these stages for you:

1) Chunk
- Split each document into manageable text chunks using a token-aware strategy.

2) Embed
- Convert each chunk to a vector with an embedding model.

3) Store
- Write vectors and associated text/metadata to a vector store (in-memory by default).

4) Search
- At query time, embed the question and perform a similarity search to retrieve top-k relevant chunks.

5) Compose Prompt
- Join retrieved snippets into a context string and pass it to an LLM for a grounded answer.

Note: You don’t need to wire these stages yourself when using the prebuilt node—they’re executed during node construction and on each query.

## Quickstart: Prebuilt RAG Node (recommended)

This is the easiest way to add RAG to your app.

```python
import railtracks as rt
from railtracks.prebuilt import rag_node
from railtracks.nodes.concrete import TerminalLLM
from railtracks.llm import OpenAILLM

# 1) Build the retrieval node
retriever = rag_node(
    ["Steve likes apples", "John likes bananas", "Alice likes oranges"],
    input_type="text",                      # "text" for raw strings, "path" for file paths
    embed_model="text-embedding-3-small",   # embedding model
    # token_count_model="gpt-4o",           # optional, for token-aware chunking
    # chunk_size=1000,                      # optional
    # chunk_overlap=200,                    # optional
)

# 2) Retrieve relevant context
question = "Who likes apples?"
search_result = rt.call_sync(retriever, question, top_k=3)  # adjust top_k as needed
context = "\n\n".join(search_result.to_list_of_texts())

# 3) Ask an LLM with the retrieved context
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

# you can invoke the LLM node like:
# answer = rt.call_sync(llm_node)
# print(answer)

print("Context:")
print(context)
```

### Some Parameters you’ll care about

- documents: List of texts or file paths.
- input_type: "text" for raw strings, "path" for UTF-8 text files.
- embed_model: Embedding model name (e.g., "text-embedding-3-small").
- token_count_model: Model used for token-aware chunking (affects chunk_size units).
- chunk_size: Approximate tokens per chunk.
- chunk_overlap: Token overlap between chunks to preserve context across boundaries.
- top_k (on query): How many chunks to retrieve for a question.

### Working with files

Use input_type="path" to load text files:
```python
retriever = rag_node(
    ["./docs/faq.txt", "./docs/policies.txt"],
    input_type="path",
    embed_model="text-embedding-3-small",
)
```
Notes:
- Files must be UTF-8 text. For PDFs or other binary formats, extract text first.
- For large corpora or advanced storage (e.g., FAISS/Qdrant), consider building a custom node (see the Reference guide) to configure a different vector store.

## What happens under the hood

When you call rag_node(...):

1) Document ingestion
- Reads your strings or files and wraps them as TextObjects.

2) Chunking
- Splits documents into chunks based on chunk_size and chunk_overlap using a token-aware strategy tied to token_count_model.

3) Embeddings
- Calls the embedding service to embed each chunk into vectors using embed_model.

4) Indexing (store)
- Writes VectorRecords (vector + text + metadata) into the default vector store (in-memory for quick starts).

5) Retrieval on query
- Embeds the query and performs a vector similarity search to get the top_k most relevant snippets.

6) Prompt composition
- You turn the retrieved snippets into a context string and pass it to your LLM.

You don’t need to manage these steps yourself with the prebuilt node; they’re executed automatically with sensible defaults.

## Choosing good settings

- Chunk size and overlap
  - Start with 600–1200 tokens; use 10–20% overlap.
  - Larger chunks capture more context but may reduce retrieval precision; smaller chunks increase precision but may fragment meaning.

- Embedding model
  - "text-embedding-3-small" is a cost-effective default.
  - Upgrade to a stronger embedding model if your queries are nuanced or your domain is specialized.

- top_k
  - 3–5 is a common starting range. Increase for fragmented content or highly diverse corpora.

- Storage
  - Default is an in-memory store (great for dev and tests).
  - For larger datasets or persistence, use a custom node and pass a different store via store_config (see Reference).
