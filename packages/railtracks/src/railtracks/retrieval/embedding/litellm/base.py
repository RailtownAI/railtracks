from __future__ import annotations

import time
from typing import Any

import litellm

from ..base import Embedding
from ..models import EmbeddingMetrics, TextEmbeddings


def _get_vector(item: Any) -> list[float]:
    """litellm returns data items as dicts or objects depending on the provider."""
    return item["embedding"] if isinstance(item, dict) else item.embedding


class LiteLLMEmbedding(Embedding):
    """Generic litellm-backed embedding provider.

    Routes to any supported provider via the ``model`` name prefix
    (e.g. ``openai/...``, ``azure/...``). ``aembed`` makes one API call per
    invocation; use ``astream_batches`` for large inputs.

    Args:
        model: LiteLLM model string (e.g. ``"openai/text-embedding-3-small"``).
        api_key: Provider API key. Falls back to the provider's environment variable.
        api_base: Override the provider's default base URL.
        api_version: API version string (required for some providers, e.g. Azure).
        **litellm_kwargs: Additional keyword arguments forwarded to
            ``litellm.aembedding``.
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
