from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, AsyncIterable

from ...utils.logging.create import get_rt_logger
from ..models import Chunk, EmbeddedChunk
from .models import EmbeddingFailure, EmbeddingResult, MultimodalInput
from ..utils import abatched

logger = get_rt_logger(__name__)


class Embedding(ABC):
    """Text embedding contract.

    Subclasses must implement ``embed``. Two additional override points:

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
        failed: list[EmbeddingFailure] | None = None,
    ) -> AsyncGenerator[EmbeddedChunk, None]:
        """Embed an async chunk stream in fixed-size batches, yielding EmbeddedChunks
        as each batch completes. Keeps memory bounded and allows downstream consumers
        (e.g. a vector store writer) to start work before the full stream is read.

        Batches that fail are logged and appended to ``failed`` (if provided)
        so the caller can inspect or requeue them. The stream continues past
        failed batches rather than raising."""
        async for batch in abatched(chunks, batch_size or self.default_batch_size):
            try:
                result = await self.aembed(batch)
                for ec in result.chunks:
                    yield ec
            except Exception as exc:
                logger.warning(
                    f"Embedding batch failed: {len(batch)} chunks will be skipped. error={exc}",
                )
                if failed is not None:
                    failed.append(EmbeddingFailure(chunks=batch, error=exc))


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
