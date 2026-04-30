from __future__ import annotations

from .base import LiteLLMEmbedding


class AzureEmbedding(LiteLLMEmbedding):
    """Azure OpenAI embedding. All three connection params are required — there
    are no sensible defaults for Azure deployments."""

    def __init__(
        self,
        deployment: str,
        *,
        api_base: str,
        api_version: str,
        api_key: str | None = None,  # falls back to AZURE_API_KEY
    ) -> None:
        super().__init__(
            model=f"azure/{deployment}",
            api_base=api_base,
            api_version=api_version,
            api_key=api_key,
        )
