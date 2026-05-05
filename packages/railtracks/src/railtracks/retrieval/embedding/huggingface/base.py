from __future__ import annotations

import time
from typing import Any

import numpy as np
from huggingface_hub import AsyncInferenceClient, InferenceClient
from huggingface_hub.inference._providers import PROVIDER_OR_POLICY_T

from ....utils.logging.create import get_rt_logger
from ..base import Embedding
from ..models import EmbeddingMetrics, TextEmbeddings

logger = get_rt_logger(__name__)


def _to_vectors(output: Any, model: str) -> list[list[float]]:
    arr = np.asarray(output)
    if arr.ndim == 3:
        logger.debug(
            "Model %r returned token-level embeddings (shape %s) — mean-pooling over sequence dimension.",
            model,
            arr.shape,
        )
        arr = arr.mean(axis=1)
    elif arr.ndim == 1:
        arr = arr.reshape(1, -1)
    return arr.tolist()


class HuggingFaceEmbedding(Embedding):
    """HuggingFace Inference API embedding via huggingface_hub.

    Uses HuggingFace's own client rather than litellm, keeping it in sync
    with their inference providers API.

    ``model`` is the HuggingFace model ID (e.g. ``sentence-transformers/all-MiniLM-L6-v2``).
    ``provider`` selects the inference provider (default: ``hf-inference``).
    ``token`` falls back to the ``HF_TOKEN`` environment variable.
    """

    default_batch_size = 32

    def __init__(
        self,
        model: str,
        *,
        provider: PROVIDER_OR_POLICY_T = "hf-inference",
        token: str | None = None,
    ) -> None:
        self._model = model
        self._sync_client = InferenceClient(provider=provider, token=token)
        self._async_client = AsyncInferenceClient(provider=provider, token=token)

    async def aembed(self, texts: list[str]) -> TextEmbeddings:
        if not texts:
            return TextEmbeddings(vectors=[], metrics=EmbeddingMetrics())
        t0 = time.perf_counter()
        output = await self._async_client.feature_extraction(texts, model=self._model)
        latency = time.perf_counter() - t0
        vectors = _to_vectors(output, self._model)
        return TextEmbeddings(
            vectors=vectors,
            metrics=EmbeddingMetrics(
                latency=latency,
                model=self._model,
                vector_count=len(vectors),
                dimension=len(vectors[0]) if vectors else None,
            ),
        )
