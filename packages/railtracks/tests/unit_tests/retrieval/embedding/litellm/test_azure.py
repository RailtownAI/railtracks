from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from litellm.types.utils import EmbeddingResponse, Usage
from railtracks.retrieval.embedding import AzureEmbedding


def _embedding_response(vectors: list[list[float]], *, model: str = "azure/my-deploy") -> EmbeddingResponse:
    data = [
        {"embedding": v, "index": i, "object": "embedding"}
        for i, v in enumerate(vectors)
    ]
    return EmbeddingResponse(
        model=model,
        data=data,
        usage=Usage(prompt_tokens=1, total_tokens=1),
    )


@pytest.mark.asyncio
async def test_azure_embedding_passes_connection_params():
    with patch(
        "litellm.aembedding", new=AsyncMock(return_value=_embedding_response([[0.1]]))
    ) as mock:
        emb = AzureEmbedding(
            deployment="my-deploy",
            api_base="https://my.openai.azure.com",
            api_version="2024-02-01",
        )
        await emb.aembed(["x"])
    kw = mock.call_args.kwargs
    assert kw["model"] == "azure/my-deploy"
    assert kw["api_base"] == "https://my.openai.azure.com"
    assert kw["api_version"] == "2024-02-01"
    assert "dimensions" not in kw


@pytest.mark.asyncio
async def test_azure_embedding_passes_dimensions():
    with patch(
        "litellm.aembedding", new=AsyncMock(return_value=_embedding_response([[0.1]]))
    ) as mock:
        emb = AzureEmbedding(
            deployment="my-deploy",
            api_base="https://my.openai.azure.com",
            api_version="2024-02-01",
            dimensions=512,
        )
        await emb.aembed(["x"])
    assert mock.call_args.kwargs["dimensions"] == 512


@pytest.mark.asyncio
async def test_azure_embedding_model_enables_cost_tracking():
    """model= maps to base_model internally; a non-zero total_cost is returned."""
    fake = _embedding_response([[0.1]], model="my-embeddings")
    with patch("litellm.aembedding", new=AsyncMock(return_value=fake)) as mock:
        emb = AzureEmbedding(
            deployment="my-embeddings",
            api_base="https://my-resource.openai.azure.com",
            api_version="2024-02-01",
            model="text-embedding-3-small",
        )
        result = await emb.aembed(["x"])
    assert "base_model" not in mock.call_args.kwargs
    assert result.metrics.total_cost is not None and result.metrics.total_cost > 0


@pytest.mark.asyncio
async def test_azure_embedding_without_model_reports_none_cost():
    """Without model=, a custom deployment name has no pricing and cost is None."""
    fake = _embedding_response([[0.1]], model="my-embeddings")
    with patch("litellm.aembedding", new=AsyncMock(return_value=fake)):
        emb = AzureEmbedding(
            deployment="my-embeddings",
            api_base="https://my-resource.openai.azure.com",
            api_version="2024-02-01",
        )
        result = await emb.aembed(["x"])
    assert result.metrics.total_cost is None
