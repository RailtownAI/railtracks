from __future__ import annotations

from .base import LiteLLMEmbedding


class OpenAIEmbedding(LiteLLMEmbedding):
    """OpenAI text embedding. Defaults to ``text-embedding-3-small``."""

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        *,
        api_key: str | None = None,  # falls back to OPENAI_API_KEY
    ) -> None:
        super().__init__(model=f"openai/{model}", api_key=api_key)
