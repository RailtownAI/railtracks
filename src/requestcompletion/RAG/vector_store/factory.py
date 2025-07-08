from __future__ import annotations

from typing import Any, Mapping, MutableMapping

from ..embedding_service import EmbeddingService
from .in_memory import InMemoryVectorStore


def create_store(
    cfg: Mapping[str, Any] = {},
    *,
    embedding_service: EmbeddingService | None = None,
):
    """
    Factory utility.
    Example cfg:
        {
            "backend": "memory"
            "metric": "cosine",
            "workspace": "~/.vector_store",
            "dim": 768
        }
    """
    backend = cfg.get("backend", "memory").lower()
    kwargs: MutableMapping[str, Any] = dict(cfg)
    kwargs.pop("backend", None)  # remove to avoid unexpected kwarg
    kwargs["embedding_service"] = embedding_service

    if backend in {"memory", "inmemory"}:
        return InMemoryVectorStore(**kwargs)

    raise ValueError(f"Unknown backend '{backend}'")
