from __future__ import annotations

import time
from typing import Any

import litellm
from dotenv import load_dotenv

from ..base import Embedding
from ..models import EmbeddingMetrics, TextEmbeddings

load_dotenv()


def _get_vector(item: Any) -> list[float]:
    """litellm returns data items as dicts or objects depending on the provider."""
    return item["embedding"] if isinstance(item, dict) else item.embedding


class LiteLLMEmbedding(Embedding):
    """Generic litellm-backed embedding. Routes to any supported provider via
    the ``model`` name prefix (e.g. ``openai/...``, ``azure/...``).

    ``aembed`` makes a single API call with whatever list it receives. Batching
    is the caller's responsibility: use ``aembed_chunks`` or ``astream_batches``
    for large inputs.

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
            for k, v in {
                "api_key": api_key,
                "api_base": api_base,
                "api_version": api_version,
                **litellm_kwargs,
            }.items()
            if v is not None
        }

    async def aembed(self, texts: list[str]) -> TextEmbeddings:
        if not texts:
            return TextEmbeddings(vectors=[], metrics=EmbeddingMetrics())
        t0 = time.perf_counter()
        response = await litellm.aembedding(
            model=self._model, input=texts, **self._kwargs
        )
        latency = time.perf_counter() - t0
        vectors = [list(_get_vector(item)) for item in response.data]
        return TextEmbeddings(
            vectors=vectors,
            metrics=self._extract_metrics(response, latency, len(vectors)),
        )

    def _extract_metrics(
        self, response: Any, latency: float, vector_count: int
    ) -> EmbeddingMetrics:
        usage = getattr(response, "usage", None)
        hidden = getattr(response, "_hidden_params", None) or {}
        data = getattr(response, "data", None) or []
        return EmbeddingMetrics(
            input_tokens=getattr(usage, "prompt_tokens", None)
            if usage is not None
            else None,
            total_cost=hidden.get("response_cost") or None,
            latency=latency,
            vector_count=vector_count,
            model=getattr(response, "model", None),
            dimension=len(_get_vector(data[0])) if data else None,
        )
