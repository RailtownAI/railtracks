# Loading Documents from Cloud Storage

This tutorial walks you through loading documents from AWS S3 or Azure Blob Storage
and connecting them to a RAG-powered agent.

!!! tip "Prerequisites"
    - You should be comfortable with the [RAG concepts](../../rag/RAG.md) and have read
      the [vector store guide](../../rag/vector_stores/vector_store_info.md).
    - Install the required extras before starting:

    ```bash
    pip install railtracks[aws]          # for S3
    pip install railtracks[azure-blob]   # for Azure Blob Storage
    pip install railtracks[chroma]       # for the vector store
    ```

---

## Step 1 — Load your documents

Pick the provider that matches your storage:

=== "AWS S3"

    ```python
    --8<-- "docs/scripts/storage_loaders.py:s3_prefix"
    ```

=== "Azure Blob Storage"

    ```python
    --8<-- "docs/scripts/storage_loaders.py:azure_prefix"
    ```

Each loader returns a list of
`Document` objects (`railtracks.retrieval.models.Document`). Every document
carries:

- **`content`** — the UTF-8 text of the file
- **`type`** — a `DocumentType` inferred from the file extension (defaults to `TEXT`)
- **`source`** — the full provider URI (e.g. `s3://bucket/key`) used for citation
- **`metadata`** — provider-specific fields (`bucket`, `key`, `container`, …)

---

## Step 2 — Index the documents in a vector store

Pass the documents straight to `ChromaVectorStore.upsert()`:

```python
--8<-- "docs/scripts/storage_loaders.py:shared_embedding"
```

```python
from railtracks.vector_stores import ChromaVectorStore

store = ChromaVectorStore("my-knowledge-base", embedding_function=embedding_function)
store.upsert(documents)
```

---

## Step 3 — Build a retrieval tool

Wrap the store's `search` method in a `function_node` so the agent can call it:

```python
import railtracks as rt

@rt.function_node
def search_docs(query: str) -> str:
    """Search the knowledge base and return relevant excerpts."""
    results = store.search(query, top_k=5)
    return "\n\n".join(r.content for r in results)
```

---

## Step 4 — Connect to an agent

```python
agent = rt.agent_node(
    name="KnowledgeAgent",
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message="Answer questions using only the provided knowledge base.",
    tool_nodes=[search_docs],
)

flow = rt.Flow("knowledge-flow", entry_point=agent)
response = flow.invoke("What is our remote work policy?")
print(response)
```

---

## Putting it all together

### S3

```python
--8<-- "docs/scripts/storage_loaders.py:pipeline_s3_to_rag"
```

### Azure Blob Storage

```python
--8<-- "docs/scripts/storage_loaders.py:pipeline_azure_to_rag"
```

---

!!! success "Next steps"
    - Explore [filtering](../../rag/vector_stores/filtering.md) to scope retrieval by
      metadata (e.g., `container`, `bucket`, `key`).
    - Add [guardrails](../../documentation/advanced/guardrails/overview.md) to validate
      agent responses before returning them to users.
    - Use [async loading](../../integrations/storage/s3.md#async-usage) (`aload` /
      `astream`) when integrating with async frameworks such as FastAPI.
