from __future__ import annotations

import asyncio
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


async def _iter_list(lst: list) -> AsyncGenerator:
    for item in lst:
        yield item


class Embedding(ABC):
    """Text embedding contract.

    Subclasses must implement ``aembed`` and declare ``default_batch_size``
    at the class level. Leaving ``default_batch_size = None`` (the default)
    requires callers to pass ``batch_size`` explicitly to ``astream_batches``.

    Override points:

    - ``default_batch_size``: set at the class level to declare the provider's
      sensible batch ceiling, used by ``astream_batches``.
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
            try:
                from IPython import get_ipython

                if get_ipython() is not None:
                    raise RuntimeError(
                        "embed() cannot be called from a Jupyter notebook; "
                        "use `result = await embedder.aembed(texts)` instead."
                    )
            except ImportError:
                pass
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
        concurrency: int = 1,
    ) -> AsyncGenerator[EmbeddingResult | EmbeddingFailure, None]:
        """Embed a chunk stream in fixed-size batches.

        Yields one ``EmbeddingResult`` per successful batch and one
        ``EmbeddingFailure`` per failed batch. The stream continues past
        failures.

        ``concurrency`` controls how many batches are sent to the provider
        simultaneously. Results are always yielded in input order. Defaults
        to 1 (serial). Raise it to hide network latency during large ingestion
        runs (e.g. ``concurrency=4`` gives ~4× throughput for network-bound
        providers like OpenAI).
        """
        bs = batch_size or self.default_batch_size
        if bs is None:
            raise ValueError(
                f"{type(self).__name__} does not declare a default_batch_size. "
                "Pass batch_size= explicitly or set default_batch_size on the class."
            )
        source = _iter_list(chunks) if isinstance(chunks, list) else chunks

        if concurrency <= 1:
            async for batch in abatched(source, bs):
                yield await self._embed_one_batch(batch)
        else:
            window: list[list[Chunk]] = []
            async for batch in abatched(source, bs):
                window.append(batch)
                if len(window) >= concurrency:
                    for result in await asyncio.gather(
                        *[self._embed_one_batch(b) for b in window]
                    ):
                        yield result
                    window.clear()
            if window:
                for result in await asyncio.gather(
                    *[self._embed_one_batch(b) for b in window]
                ):
                    yield result


class SyncEmbedding(Embedding, ABC):
    """Mixin for providers that only expose a blocking API.

    Implement ``_embed_sync``; ``aembed`` wraps it in ``asyncio.to_thread``.
    """

    @abstractmethod
    def _embed_sync(self, texts: list[str]) -> TextEmbeddings: ...

    async def aembed(self, texts: list[str]) -> TextEmbeddings:
        return await asyncio.to_thread(self._embed_sync, texts)
