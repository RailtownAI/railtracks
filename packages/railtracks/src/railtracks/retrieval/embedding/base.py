from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, AsyncIterable

from ...utils.logging.create import get_rt_logger
from ..models import Chunk, EmbeddedChunk
from ..utils import abatched
from .models import (
    EmbeddingFailure,
    EmbeddingMetrics,
    EmbeddingResult,
    MultimodalInput,
    TextEmbeddings,
)

logger = get_rt_logger(__name__)


async def _iter_list(lst: list) -> AsyncGenerator:
    for item in lst:
        yield item


class Embedding(ABC):
    """Text embedding contract.

    Subclasses must implement ``aembed``. Override points:

    - ``default_batch_size``: set at the class level to declare the provider's
      sensible batch ceiling, used by ``aembed_chunks`` and ``astream_batches``.
    """

    default_batch_size: int = 64

    @abstractmethod
    async def aembed(self, texts: list[str]) -> TextEmbeddings: ...

    def embed(self, texts: list[str]) -> TextEmbeddings:
        """Sync embed. Raises if called from an async context."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError(
                "embed() cannot be called from an async context; use aembed() instead"
            )
        return asyncio.run(self.aembed(texts))

    async def aembed_query(self, text: str) -> list[float]:
        """Embed a single query string, returning one vector."""
        result = await self.aembed([text])
        return result.vectors[0]

    def embed_query(self, text: str) -> list[float]:
        """Sync embed_query. Raises if called from an async context."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError(
                "embed_query() cannot be called from an async context; use aembed_query() instead"
            )
        return asyncio.run(self.aembed_query(text))

    async def aembed_chunks(self, chunks: list[Chunk]) -> EmbeddingResult:
        """Embed chunks in batches of ``default_batch_size``, accumulating metrics."""
        if not chunks:
            return EmbeddingResult(chunks=[], metrics=EmbeddingMetrics())
        all_embedded: list[EmbeddedChunk] = []
        all_metrics: list[EmbeddingMetrics] = []
        bs = self.default_batch_size
        for i in range(0, len(chunks), bs):
            batch = chunks[i : i + bs]
            text_result = await self.aembed([c.content for c in batch])
            model_name = text_result.metrics.model or ""
            all_embedded.extend(
                EmbeddedChunk(chunk=chunk, vector=vec, embedding_model=model_name)
                for chunk, vec in zip(batch, text_result.vectors)
            )
            all_metrics.append(text_result.metrics)
        return EmbeddingResult(
            chunks=all_embedded,
            metrics=sum(all_metrics, EmbeddingMetrics()),
        )

    async def astream_batches(
        self,
        chunks: list[Chunk] | AsyncIterable[Chunk],
        batch_size: int | None = None,
    ) -> AsyncGenerator[EmbeddingResult | EmbeddingFailure, None]:
        """Embed an async chunk stream in fixed-size batches, yielding one
        ``EmbeddingResult`` per successful batch and ``EmbeddingFailure`` per
        failed batch. The stream continues past failures."""
        bs = batch_size or self.default_batch_size
        source = _iter_list(chunks) if isinstance(chunks, list) else chunks
        async for batch in abatched(source, bs):
            try:
                text_result = await self.aembed([c.content for c in batch])
            except Exception as exc:
                logger.warning(
                    f"Embedding batch failed: {len(batch)} chunks will be skipped. error={exc}",
                )
                yield EmbeddingFailure(chunks=batch, error=exc)
                continue
            model_name = text_result.metrics.model or ""
            embedded = [
                EmbeddedChunk(chunk=chunk, vector=vec, embedding_model=model_name)
                for chunk, vec in zip(batch, text_result.vectors)
            ]
            yield EmbeddingResult(chunks=embedded, metrics=text_result.metrics)

    async def astream_chunks(
        self,
        chunks: list[Chunk] | AsyncIterable[Chunk],
        batch_size: int | None = None,
    ) -> AsyncGenerator[EmbeddedChunk, None]:
        """Flat version of ``astream_batches``. Yields ``EmbeddedChunk`` objects
        and re-raises any batch failure rather than swallowing it."""
        async for result in self.astream_batches(chunks, batch_size):
            if isinstance(result, EmbeddingFailure):
                raise result.error
            for ec in result.chunks:
                yield ec


class SyncEmbedding(Embedding, ABC):
    """Mixin for providers that only expose a blocking API.

    Implement ``_embed_sync``; ``aembed`` wraps it in ``asyncio.to_thread``.
    """

    @abstractmethod
    def _embed_sync(self, texts: list[str]) -> TextEmbeddings: ...

    async def aembed(self, texts: list[str]) -> TextEmbeddings:
        return await asyncio.to_thread(self._embed_sync, texts)


class MultimodalEmbedder(Embedding, ABC):
    """Extends Embedding with image support. Reserved for providers (e.g. Voyage)
    that accept image inputs alongside text. No concrete implementation yet.

    Subclasses must implement ``embed_multimodal``. As with ``Embedding.aembed``,
    override ``aembed_multimodal`` directly if the provider has a native async path.
    """

    @abstractmethod
    def embed_multimodal(self, inputs: list[MultimodalInput]) -> EmbeddingResult: ...

    async def aembed_multimodal(self, inputs: list[MultimodalInput]) -> EmbeddingResult:
        return await asyncio.to_thread(self.embed_multimodal, inputs)
