# Retrieval

Retrieval allows you to provide context to an agent or to do general queries on a previously ingested knowledge base. After initliazation of your runtime to connect to the vectorized knowledge base, `runtime.retrieve(...)` will return `RetrievalResult` which contains a list of `RetrievedChunk`s

______________________________________________________________________

## Vector search

```python
import asyncio

from railtracks.retrieval import RetrievalRuntime


async def query(runtime: RetrievalRuntime):
    result = await runtime.retrieve(
        "What is the refund policy?",
        top_k=5,
    )

    print(f"query={result.query}")
    for hit in result.chunks:
        print(f"  [{hit.score:.3f}] {hit.chunk.content[:120]}")
```

`RetrievalResult` is `{query, chunks}` where each `RetrievedChunk` carries a `score` in `[0, 1]`, a 0-indexed `rank`, and the original `Chunk` (content

- metadata + `document_id`).

`RetrievalResult` also exposes `embedding_metrics` (an `EmbeddingMetrics` from `railtracks.retrieval`), which records the token count, estimated cost, latency, and model name for the query embedding call. It is `None` only when the embedder reports no metrics.

The runtime caches the embedder's reported model name on the first successful ingest. If a later retrieve uses a runtime whose embedder reports a different model, you get `EmbeddingModelMismatchError` signaling corruption of the vector spaces.

______________________________________________________________________

## Metadata filters

Any scalar in `Chunk.metadata` is filterable. The runtime also writes two well-known keys automatically (`source_path` (from `Document.source`) and `content_hash`) so you can filter by source without setting metadata yourself:

```python
async def filtered(runtime: RetrievalRuntime):
    # Filters are flat equality on Chunk.metadata.
    # The runtime also writes source_path and content_hash automatically.
    result = await runtime.retrieve(
        "flood coverage exclusions",
        top_k=5,
        metadata_filters={
            "jurisdiction": "TX",
            "doc_type": "regulation",
        },
    )
    return result
```

These two keys belong to the runtime: if a loader puts a `source_path` or `content_hash` column into the metadata, the runtime's value replaces it and a warning is logged. Every key in `metadata_filters` refers to `Chunk.metadata` (apart from `scope_<label>` keys, which narrow by one scope label), even one named like an entry field: `{"document_id": "42"}` matches a `document_id` metadata column, not the internal document id. To restrict a search to one document, filter on its `source_path`.

Filters are flat equality only

Currently we only support `field==value` for filtering. For other common filtering needs (`or`, `is_in`, etc) please open an issue or a PR at https://github.com/RailtownAI/railtracks/issues

______________________________________________________________________

## Per-call scope

When the same runtime serves multiple users, pass `StoreScope` on each `retrieve()` (and `ingest()`) call to isolate their results:

```python
from railtracks.retrieval.stores import StoreScope  # noqa: E402


async def scoped_query(runtime: RetrievalRuntime):
    # Scope is per-call. One runtime serves any number of tenants —
    # each call filters reads (and tags writes) by the scope you pass.
    alice_hits = await runtime.retrieve(
        "policy update",
        scope=StoreScope(labels={"user_id": "alice"}),
    )
    bob_hits = await runtime.retrieve(
        "policy update",
        scope=StoreScope(labels={"user_id": "bob"}),
    )
    return alice_hits, bob_hits
```

Scope is enforced at the store layer, not the runtime, so even a direct `VectorStore.read()` call honors it. And unlike metadata filters, scope is stamped onto entries at write time, not just applied at read time.

A scope matches entries written with exactly the same labels, and `metadata_filters` can't widen it. `retrieve()` without a scope (or with `StoreScope()`) searches only unscoped entries, so forgetting the scope never returns another tenant's data. To search every scope, for example from an admin tool, pass `ALL_SCOPES` (from `railtracks.retrieval`) explicitly.

______________________________________________________________________

## Audit hook

`on_retrieve=callback` fires synchronously after every `retrieve()` call, with `(query: str, result: RetrievalResult)`. Use it for query logs, hit-rate metrics, or feeding queries into an evaluation harness:

```python
from railtracks.retrieval import RetrievalRuntime  # noqa: E402, F811
from railtracks.retrieval.chunking import RecursiveCharacterChunker  # noqa: E402
from railtracks.retrieval.embedding import OpenAIEmbedding  # noqa: E402
from railtracks.retrieval.stores import InMemoryVectorBackend, VectorStore  # noqa: E402


def log_retrieve(query: str, result):
    # Synchronous; runs after the retrieve call returns. Use for query-side
    # audit logging, hit-rate metrics, or feeding an evaluation harness.
    print(f"[retrieve] {query!r} → {len(result.chunks)} hits")


def build_with_hook():
    return RetrievalRuntime(
        chunker=RecursiveCharacterChunker(chunk_size=800),
        embedder=OpenAIEmbedding(),
        store=VectorStore(InMemoryVectorBackend()),
        on_retrieve=log_retrieve,
    )
```

Like `on_ingest`, it runs on the request path. Push to a queue for any non-trivial work.

______________________________________________________________________

## Wiring retrieval into an agent

`runtime.retrieve()` is the only primitive and there's no built-in "RAG mode" you have to opt into. Two patterns cover most uses:

**As a tool the agent calls deliberately.** The agent decides when it needs context and what to search for. Best when only some turns need retrieval (general chat with occasional doc lookups), or when you want the model to refine queries before each search:

```python
import railtracks as rt  # noqa: E402


def build_docs_bot(runtime: RetrievalRuntime):
    # The LLM decides when to call this and what to search for.
    # Best when only some turns need retrieval, or you want the model to
    # refine the query before each search.
    @rt.function_node
    async def search_docs(query: str, top_k: int = 5) -> str:
        """Search the documentation. Returns the most relevant chunks, separated by ---."""
        result = await runtime.retrieve(query, top_k=top_k)
        return "\n\n---\n\n".join(hit.chunk.content for hit in result.chunks)

    return rt.agent_node(
        name="DocsBot",
        llm=rt.llm.OpenAILLM("gpt-6-luna"),
        system_message=(
            "Use search_docs to ground every factual answer. "
            "Cite retrieved chunks verbatim."
        ),
        tool_nodes=[search_docs],
    )
```

**As a pre-invoke step that always injects context.** Retrieval runs on every agent invocation, transparent to the model. Best when the LLM should ground answers in the corpus on every turn (docs bots, support assistants):

```python
async def ask_with_context(agent_cls, runtime: RetrievalRuntime, question: str):
    # Run retrieval yourself, then call the agent with the augmented prompt.
    # Best when the LLM should ground answers in the corpus on every turn
    # without having to decide whether to search.
    result = await runtime.retrieve(question, top_k=5)
    context = "\n\n---\n\n".join(hit.chunk.content for hit in result.chunks)

    return await rt.call(
        agent_cls,
        user_input=f"Context:\n{context}\n\nQuestion: {question}",
    )
```

Neither pattern hides the retrieval call; you control the query, the `top_k`, the filters, and where the chunks land in the prompt. Swap embedders, chunkers, or stores by passing a different runtime to the agent.

`RagConfig` has been removed

Earlier versions exposed a `RagConfig` shortcut that wired the pre-invoke pattern in one line. It has been removed; the patterns above are the supported way to attach retrieval to an agent.

______________________________________________________________________

## Related

- **[Ingestion](https://docs.railtracks.org/retrieval/runtime/ingestion/index.md)**: the write path: streaming events, re-ingest, multi-tenant writes, sanitization, token guards.
- **[Components → Stores](https://docs.railtracks.org/retrieval/components/stores/base/index.md)**: the `Store` protocol, `StoreQuery`, and direct vector search with `read`.
- **[Components → Design](https://docs.railtracks.org/retrieval/components/design/index.md)**: embedding-model guard, staleness check, what's not in scope yet (boolean filters, hybrid search, built-in reranker).
