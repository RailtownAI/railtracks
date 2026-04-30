from __future__ import annotations

from .base import LiteLLMEmbedding


class OllamaEmbedding(LiteLLMEmbedding):
    """Ollama embedding. Defaults to ``nomic-embed-text`` and a local server.

    Ollama processes one request at a time, so ``default_batch_size`` is 1.
    """

    default_batch_size = 1

    def __init__(
        self,
        model: str = "nomic-embed-text",
        *,
        api_base: str = "http://localhost:11434",
    ) -> None:
        super().__init__(model=f"ollama/{model}", api_base=api_base)
