from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Iterable, List, Optional, Sequence

import litellm

logger = logging.getLogger(__name__)


class BaseEmbeddingService(ABC):
    """
    Base class for embedding services.
    """

    @abstractmethod
    def embed(self, texts: Sequence[str], *, batch_size: int = 8) -> List[List[float]]:
        raise NotImplementedError("Subclasses must implement this method.")

    def __repr__(self):
        return f"{self.__class__.__name__}(model={self.model})"


class EmbeddingService(BaseEmbeddingService):
    """
    Embedding service that uses litellm to perform embedding tasks.
    """

    DEFAULT_MODEL = "text-embedding-3-small"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        *,
        # --- litellm-specific kwargs ---
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = 60,
        **litellm_extra: Any,
    ):
        """
        Initialize the embedding service.

        Args:
            model: Model name (OpenAI, TogetherAI, etc.)
            api_key: If None, taken from OPENAI_API_KEY env var.
            base_url: Override OpenAI base URL if using gateway / proxy.
            timeout: Per-request timeout in seconds.
            **litellm_extra: Any other args passed straight to litellm.embedding
                            (e.g. headers, organization, etc.)
        """
        self.model = model
        self.litellm_extra = {
            "api_key": api_key or None,
            "base_url": base_url,
            "timeout": timeout,
            **litellm_extra,
        }

    # ─────────────────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────────────────

    def embed(self, texts: Sequence[str], *, batch_size: int = 8) -> List[List[float]]:
        """
        Convenience wrapper to embed many short texts in one go.
        Accepts either a sequence of strings or a single string.
        """
        if isinstance(texts, (str, bytes)):
            texts = [str(texts)]

        if not isinstance(texts, Sequence):
            raise TypeError("texts must be a sequence of strings or a single string")

        if batch_size <= 0:
            raise ValueError("batch_size must be a positive integer")

        vectors: List[List[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            vectors.extend(self._embed_batch(batch))
        return vectors

    # ─────────────────────────────────────────────────────
    # INTERNAL HELPERS
    # ─────────────────────────────────────────────────────
    def _embed_batch(self, batch: Iterable[str]) -> List[List[float]]:
        """
        Low-level wrapper around litellm.embedding
        """
        batch_list = list(batch)
        if not batch_list:
            return []

        try:
            response = litellm.embedding(
                model=self.model,
                input=batch_list,
                **{k: v for k, v in self.litellm_extra.items() if v is not None},
            )
        except Exception as e:
            logger.exception("Embedding request failed: %s", e)
            raise

        # litellm typically returns a dict with 'data' or an object with .data
        data = getattr(response, "data", None)
        if data is None and isinstance(response, dict):
            data = response.get("data")

        if data is None:
            raise ValueError("Unexpected embedding response format: missing 'data'")

        # Normalize items to (index, embedding) and maintain order
        indexed: List[tuple[int, List[float]]] = []
        for i, item in enumerate(data):
            if isinstance(item, dict):
                idx = item.get("index", i)
                emb = item.get("embedding")
            else:
                idx = getattr(item, "index", i)
                emb = getattr(item, "embedding", None)

            if emb is None:
                raise ValueError(
                    "Unexpected embedding item format: missing 'embedding'"
                )

            indexed.append((idx, list(emb)))

        indexed.sort(key=lambda t: t[0])
        vectors = [emb for _, emb in indexed]
        return vectors
