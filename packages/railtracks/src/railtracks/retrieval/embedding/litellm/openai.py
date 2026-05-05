from __future__ import annotations

from typing import Any

from .base import LiteLLMEmbedding


class OpenAIEmbedding(LiteLLMEmbedding):
    """OpenAI text embedding. Defaults to ``text-embedding-3-small``.

    ``dimensions`` truncates the output vector (supported by ``text-embedding-3-*`` models only).
    """

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        *,
        api_key: str | None = None,  # falls back to OPENAI_API_KEY
        dimensions: int | None = None,
    ) -> None:
        extra: dict[str, Any] = {}
        if dimensions is not None:
            extra["dimensions"] = dimensions
        super().__init__(model=f"openai/{model}", api_key=api_key, **extra)
