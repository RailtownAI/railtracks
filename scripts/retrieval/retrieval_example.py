"""Retrieval-side examples used by docs/retrieval/retrieval.md."""


# --8<-- [start:basic]
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
# --8<-- [end:basic]


# --8<-- [start:metadata_filters]
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
# --8<-- [end:metadata_filters]


# --8<-- [start:scope_override]
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
# --8<-- [end:scope_override]


# --8<-- [start:on_retrieve_hook]
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
# --8<-- [end:on_retrieve_hook]


# --8<-- [start:as_tool]
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
        llm=rt.llm.OpenAILLM("gpt-4o"),
        system_message=(
            "Use search_docs to ground every factual answer. "
            "Cite retrieved chunks verbatim."
        ),
        tool_nodes=[search_docs],
    )
# --8<-- [end:as_tool]


# --8<-- [start:as_pre_invoke]
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
# --8<-- [end:as_pre_invoke]
