from __future__ import annotations

from typing import Any

from .base import LiteLLMEmbedding


class AzureEmbedding(LiteLLMEmbedding):
    """Azure OpenAI embedding.

    Args:
        deployment: Azure deployment name.
        api_base: Azure OpenAI endpoint URL.
        api_version: Azure OpenAI API version string.
        api_key: Azure API key. Falls back to ``AZURE_API_KEY``.
        dimensions: Truncate output vectors to this size. Only supported by
            ``text-embedding-3-*`` models.
        base_model: Underlying Azure model id used for cost mapping when the
            deployment name is custom (forwarded to
            ``litellm.completion_cost``).
    """

    def __init__(
        self,
        deployment: str,
        *,
        api_base: str,
        api_version: str,
        api_key: str | None = None,  # falls back to AZURE_API_KEY
        dimensions: int | None = None,
        base_model: str | None = None,
    ) -> None:
        extra: dict[str, Any] = {}
        if dimensions is not None:
            extra["dimensions"] = dimensions
        if base_model is not None:
            extra["base_model"] = base_model
        super().__init__(
            model=f"azure/{deployment}",
            api_base=api_base,
            api_version=api_version,
            api_key=api_key,
            **extra,
        )
