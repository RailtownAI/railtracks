"""Minimal end-to-end retrieval example used by docs/retrieval/index.md."""

from rich import print
# --8<-- [start:minimal]
import asyncio

from railtracks.retrieval import RetrievalRuntime
from railtracks.retrieval.chunking import SentenceChunker
from railtracks.retrieval.embedding import OpenAIEmbedding
from railtracks.retrieval.loaders import TextLoader
from railtracks.retrieval.stores import InMemoryVectorBackend, VectorStore


async def main():
    runtime = RetrievalRuntime(
        chunker=SentenceChunker(chunk_size=7, overlap=2),
        embedder=OpenAIEmbedding(model="text-embedding-3-small"),
        store=VectorStore(InMemoryVectorBackend()),
        batch_size=16,  # smaller batch size for faster embedding in this example
    )

    stats = await runtime.ingest_all(loader=TextLoader("./docs"))
    print(f"ingested {stats.documents_loaded} docs / {stats.chunks_embedded} chunks")

    result = await runtime.retrieve("how do I configure observability?", top_k=5)
    for hit in result.chunks:
        print(f"  [{hit.score:.3f}] {hit.chunk.content}")


asyncio.run(main())
# --8<-- [end:minimal]
