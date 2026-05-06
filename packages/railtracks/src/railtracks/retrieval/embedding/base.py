from __future__ import annotations

import asyncio
from typing import TypeVar
import sys
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, AsyncIterable

from ...utils.logging.create import get_rt_logger
from ..models import Chunk, EmbeddedChunk
from ..utils import abatched
from .models import (
    EmbeddingFailure,
    EmbeddingResult,
    TextEmbeddings,
)

logger = get_rt_logger(__name__)

_T = TypeVar("_T")
async def _to_async_iterable(lst: list[_T]) -> AsyncGenerator[_T, None]:
    for item in lst:
        yield item


class Embedding(ABC):
    """Text embedding contract.

    Subclasses must implement ``aembed`` and declare ``default_batch_size``
    at the class level.

    Attributes:
        default_batch_size: Provider's sensible batch ceiling used by
            ``astream_batches``. Subclasses should override at the class level.
            ``None`` requires callers to pass ``batch_size`` explicitly.
    """

    default_batch_size: int | None = None

    @abstractmethod
    async def aembed(self, texts: list[str]) -> TextEmbeddings: ...

    def embed(self, texts: list[str]) -> TextEmbeddings:
        """Sync embed. Raises if called from an async context."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            if "ipykernel" in sys.modules:
                raise RuntimeError(
                    "embed() cannot be called from a Jupyter notebook; "
                    "use `result = await embedder.aembed(texts)` instead."
                )
            raise RuntimeError(
                "embed() cannot be called from an async context; use `await aembed()` instead."
            )
        return asyncio.run(self.aembed(texts))

    async def _embed_one_batch(
        self, batch: list[Chunk]
    ) -> EmbeddingResult | EmbeddingFailure:
        try:
            text_result = await self.aembed([c.content for c in batch])
            if len(text_result.vectors) != len(batch):
                raise ValueError(
                    f"Provider returned {len(text_result.vectors)} vectors for {len(batch)} inputs"
                )
            model_name = text_result.metrics.model or ""
            embedded = [
                EmbeddedChunk(chunk=c, vector=v, embedding_model=model_name)
                for c, v in zip(batch, text_result.vectors)
            ]
            return EmbeddingResult(chunks=embedded, metrics=text_result.metrics)
        except Exception as exc:
            logger.warning(
                "Embedding batch failed: %d chunks will be skipped. error=%s",
                len(batch),
                exc,
            )
            return EmbeddingFailure(chunks=batch, errors=[exc])

    async def astream_batches(
        self,
        chunks: list[Chunk] | AsyncIterable[Chunk],
        batch_size: int | None = None,
    ) -> AsyncGenerator[EmbeddingResult | EmbeddingFailure, None]:
        """Embed a chunk stream in fixed-size batches.

        The stream continues past failures; each batch yields either a result
        or a failure record with the source chunks.

        Args:
            chunks: Source chunks as a list or async iterable.
            batch_size: Items per batch. Falls back to ``default_batch_size``
                when omitted; raises if neither is set.

        Yields:
            EmbeddingResult | EmbeddingFailure: One per batch — a result on
                success or a failure record on error.
        """
        bs = batch_size if batch_size is not None else self.default_batch_size
        if bs is None:
            raise ValueError(
                f"{type(self).__name__} does not declare a default_batch_size. "
                "Pass batch_size= explicitly or set default_batch_size on the class."
            )
        source = _to_async_iterable(chunks) if isinstance(chunks, list) else chunks
        async for batch in abatched(source, bs):
            yield await self._embed_one_batch(batch)


class SyncEmbedding(Embedding, ABC):
    """Mixin for providers that only expose a blocking API.

    Implement ``_embed_sync``; ``aembed`` wraps it in ``asyncio.to_thread``.
    """

    @abstractmethod
    def _embed_sync(self, texts: list[str]) -> TextEmbeddings: ...

    async def aembed(self, texts: list[str]) -> TextEmbeddings:
        return await asyncio.to_thread(self._embed_sync, texts)
