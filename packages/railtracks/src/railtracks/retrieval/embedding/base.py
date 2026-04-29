from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, AsyncIterable

from ..models import Chunk, EmbeddedChunk
from .models import EmbeddingResult, MultimodalInput
from ..utils import abatched


class Embedding(ABC):
    """Text embedding contract.

    Subclasses must implement ``embed``. Two additional class-level override
    points are available:

    - ``aembed``: override if the provider has a native async API 
      to avoid the default ``asyncio.to_thread`` wrapper.
    - ``default_batch_size``: set at the class level to declare the provider's
      sensible batch ceiling, used by ``astream_chunks`` when no explicit
      ``batch_size`` is passed.
    """

    default_batch_size: int = 64

    @abstractmethod
    def embed(self, chunks: list[Chunk]) -> EmbeddingResult: ...

    async def aembed(self, chunks: list[Chunk]) -> EmbeddingResult:
        """Async embed. Override this if the provider has a native async path."""
        return await asyncio.to_thread(self.embed, chunks)

    async def astream_chunks(
        self,
        chunks: AsyncIterable[Chunk],
        batch_size: int | None = None,
    ) -> AsyncGenerator[EmbeddedChunk, None]:
        """Embed an async chunk stream in fixed-size batches, yielding EmbeddedChunks
        as each batch completes. Keeps memory bounded and allows downstream consumers
        (e.g. a vector store writer) to start work before the full stream is read."""
        async for batch in abatched(chunks, batch_size or self.default_batch_size):
            result = await self.aembed(batch)
            for ec in result.chunks:
                yield ec


class MultimodalEmbedding(Embedding, ABC):
    """Extends Embedding with image support. Reserved for providers (e.g. Voyage)
    that accept image inputs alongside tex t. No concrete implementation yet.

    Subclasses must implement ``embed_multimodal``. As with ``Embedding.aembed``,
    override ``aembed_multimodal`` directly if the provider has a native async path.
    """

    @abstractmethod
    def embed_multimodal(self, inputs: list[MultimodalInput]) -> EmbeddingResult: ...

    async def aembed_multimodal(
        self, inputs: list[MultimodalInput]
    ) -> EmbeddingResult:
        """Async multimodal embed. Override this if the provider has a native async path."""
        return await asyncio.to_thread(self.embed_multimodal, inputs)
