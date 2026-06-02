from uuid import uuid4

from railtracks.retrieval import Chunk
from railtracks.retrieval.stores import InMemoryVectorBackend, VectorStore

chunks = [Chunk(content="Example chunk", document_id=uuid4())]
vector_store = VectorStore(backend=InMemoryVectorBackend())


# --8<-- [start:quickstart]
from railtracks.retrieval.embedding import OpenAIEmbedding

embedder = OpenAIEmbedding()  # reads OPENAI_API_KEY from environment

async def wrapper(query: list[str]):
    result = await embedder.aembed(query)
    print(result.vectors[0][:5])   # first 5 dims of the vector
    print(result.metrics)
# --8<-- [end:quickstart]


async def example_embedding():
# --8<-- [start:batch]
    from railtracks.retrieval.stores import StoreEntry
    from railtracks.retrieval.embedding import (
        EmbeddingFailure,
        EmbeddingResult,
        OpenAIEmbedding,
    )

    embedder = OpenAIEmbedding()

    async for result in embedder.astream_batches(chunks, batch_size=100):
        if isinstance(result, EmbeddingResult):
            for chunk in result.chunks:
                entry = StoreEntry.from_chunk(chunk)
                await vector_store.write(entry)
                print(result.metrics)
        else:
            print(f"Batch failed: {result.errors}")
# --8<-- [end:batch]
class Client():
    def encode(self, texts: list[str]) -> list[list[float]]:
        # Blocking call to external service.
        ...
my_blocking_client = Client()
# --8<-- [start:blocking]
from railtracks.retrieval.embedding import SyncEmbedding, TextEmbeddings


class MyBlockingEmbedder(SyncEmbedding):
    default_batch_size = 64

    def _embed_sync(self, texts: list[str]) -> TextEmbeddings:
        vectors = my_blocking_client.encode(texts)
        return TextEmbeddings(vectors=vectors)
# --8<-- [end:blocking]

# --8<-- [start:openai]
from railtracks.retrieval.embedding import OpenAIEmbedding

# Default: small model, full dimensionality
embedder = OpenAIEmbedding()

# Large model with truncated vectors (smaller storage, slight quality cost)
embedder = OpenAIEmbedding(model="text-embedding-3-large", dimensions=256)
# --8<-- [end:openai]

# --8<-- [start:azure]
from railtracks.retrieval.embedding import AzureEmbedding

embedder = AzureEmbedding(
    deployment="my-embedding-deployment",
    api_base="https://my-resource.openai.azure.com",
    api_version="2024-02-01",
)
# --8<-- [end:azure]

# --8<-- [start:ollama]
from railtracks.retrieval.embedding import OllamaEmbedding

# Local server, default model
embedder = OllamaEmbedding()

# Different model or remote Ollama instance
embedder = OllamaEmbedding(model="mxbai-embed-large", api_base="http://gpu-box:11434")
# --8<-- [end:ollama]

# --8<-- [start:litellm]
from railtracks.retrieval.embedding import LiteLLMEmbedding

embedder = LiteLLMEmbedding(
    model="cohere/embed-english-v3.0",
    api_key="...",
)
# --8<-- [end:litellm]

class MyAsyncClient():
    async def encode(self, texts: list[str]) -> list[list[float]]:
        # Async call to external service.
        ...
my_async_client = MyAsyncClient()

# --8<-- [start:custom_async]
from railtracks.retrieval.embedding import Embedding, EmbeddingMetrics, TextEmbeddings


class MyEmbedding(Embedding):
    default_batch_size = 64

    async def aembed(self, texts: list[str]) -> TextEmbeddings:
        vectors = await my_async_client.encode(texts)
        return TextEmbeddings(
            vectors=vectors,
            metrics=EmbeddingMetrics(vector_count=len(vectors)),
        )
# --8<-- [end:custom_async]

# --8<-- [start:custom_sync]
from railtracks.retrieval.embedding import SyncEmbedding, TextEmbeddings


class MyBlockingEmbedding(SyncEmbedding):
    default_batch_size = 32

    def _embed_sync(self, texts: list[str]) -> TextEmbeddings:
        vectors = my_blocking_client.encode(texts)
        return TextEmbeddings(vectors=vectors)
# --8<-- [end:custom_sync]
