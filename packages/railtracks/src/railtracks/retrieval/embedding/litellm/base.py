from __future__ import annotations

import time
from typing import Any

import litellm
from dotenv import load_dotenv

from ....retrieval.models import Chunk, EmbeddedChunk
from ..base import Embedding
from ..models import EmbeddingMetrics, EmbeddingResult

load_dotenv()


def _get_vector(item: Any) -> list[float]:
    """litellm returns data items as dicts or objects depending on the provider."""
    return item["embedding"] if isinstance(item, dict) else item.embedding


class LiteLLMEmbedding(Embedding):
    """Generic litellm-backed embedding. Routes to any supported provider via
    the ``model`` name prefix (e.g. ``openai/...``, ``azure/...``).

    ``embed`` and ``aembed`` make a single API call with whatever list they
    receive. Batching is the caller's responsibility: use ``astream_chunks``
    for large inputs, which batches the stream using ``default_batch_size``.

    Subclasses should override ``default_batch_size`` at the class level to
    declare the provider's sensible batch ceiling.
    """

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        api_base: str | None = None,
        api_version: str | None = None,
        **litellm_kwargs: Any,
    ) -> None:
        self._model = model
        self._kwargs: dict[str, Any] = {
            k: v
            for k, v in {"api_key": api_key, "api_base": api_base, "api_version": api_version, **litellm_kwargs}.items()
            if v is not None
        }

    def embed(self, chunks: list[Chunk]) -> EmbeddingResult:
        if not chunks:
            return EmbeddingResult(chunks=[], metrics=EmbeddingMetrics())
        t0 = time.perf_counter()
        response = litellm.embedding(model=self._model, input=[c.content for c in chunks], **self._kwargs)
        latency = time.perf_counter() - t0
        embedded = [
            EmbeddedChunk(chunk=chunk, vector=list(_get_vector(item)), embedding_model=self._model)
            for chunk, item in zip(chunks, response.data)
        ]
        return EmbeddingResult(chunks=embedded, metrics=self._extract_metrics(response, latency, len(embedded)))

    async def aembed(self, chunks: list[Chunk]) -> EmbeddingResult:
        if not chunks:
            return EmbeddingResult(chunks=[], metrics=EmbeddingMetrics())
        t0 = time.perf_counter()
        response = await litellm.aembedding(model=self._model, input=[c.content for c in chunks], **self._kwargs)
        latency = time.perf_counter() - t0
        embedded = [
            EmbeddedChunk(chunk=chunk, vector=list(_get_vector(item)), embedding_model=self._model)
            for chunk, item in zip(chunks, response.data)
        ]
        return EmbeddingResult(chunks=embedded, metrics=self._extract_metrics(response, latency, len(embedded)))

    def _extract_metrics(self, response: Any, latency: float, vector_count: int) -> EmbeddingMetrics:
        usage = getattr(response, "usage", None)
        hidden = getattr(response, "_hidden_params", None) or {}
        data = getattr(response, "data", None) or []
        return EmbeddingMetrics(
            input_tokens=getattr(usage, "prompt_tokens", None),
            total_cost=hidden.get("response_cost"),
            latency=latency,
            model=getattr(response, "model", None),
            vector_count=vector_count,
            dimension=len(_get_vector(data[0])) if data else None,
        )
