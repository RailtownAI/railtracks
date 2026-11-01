from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from litellm.types.utils import EmbeddingResponse, Usage
from railtracks.retrieval.embedding import (
    EmbeddingMetrics,
    LiteLLMEmbedding,
    TextEmbeddings,
)


def _embedding_response(
    vectors: list[list[float]],
    *,
    prompt_tokens: int = 10,
    model: str = "openai/text-embedding-3-small",
) -> EmbeddingResponse:
    data = [
        {"embedding": v, "index": i, "object": "embedding"}
        for i, v in enumerate(vectors)
    ]
    return EmbeddingResponse(
        model=model,
        data=data,
        usage=Usage(prompt_tokens=prompt_tokens, total_tokens=prompt_tokens),
    )


@pytest.mark.asyncio
async def test_aembed_returns_text_embeddings():
    fake = _embedding_response([[0.1, 0.2], [0.3, 0.4]])
    with patch("litellm.aembedding", new=AsyncMock(return_value=fake)):
        emb = LiteLLMEmbedding(model="openai/text-embedding-3-small")
        result = await emb.aembed(["a", "b"])

    assert isinstance(result, TextEmbeddings)
    assert result.vectors == [[0.1, 0.2], [0.3, 0.4]]


@pytest.mark.asyncio
async def test_aembed_empty_returns_empty():
    emb = LiteLLMEmbedding(model="openai/text-embedding-3-small")
    result = await emb.aembed([])
    assert result.vectors == []
    assert isinstance(result.metrics, EmbeddingMetrics)


@pytest.mark.asyncio
async def test_aembed_metrics_populated():
    fake = _embedding_response([[0.1, 0.2]], prompt_tokens=7)
    with patch("litellm.aembedding", new=AsyncMock(return_value=fake)):
        emb = LiteLLMEmbedding(model="openai/text-embedding-3-small")
        result = await emb.aembed(["hello"])

    m = result.metrics
    assert m.input_tokens == 7
    assert m.total_cost is not None and m.total_cost > 0
    assert m.latency is not None and m.latency >= 0
    assert m.vector_count == 1
    assert m.dimension == 2


@pytest.mark.asyncio
async def test_aembed_metrics_graceful_when_fields_missing():
    bare = SimpleNamespace(data=[SimpleNamespace(embedding=[0.1])], model=None)
    with patch("litellm.aembedding", new=AsyncMock(return_value=bare)):
        with patch("litellm.completion_cost", side_effect=Exception("unmapped")):
            emb = LiteLLMEmbedding(model="openai/text-embedding-3-small")
            result = await emb.aembed(["x"])

    assert result.metrics.input_tokens is None
    assert result.metrics.total_cost is None


@pytest.mark.asyncio
async def test_zero_cost_is_preserved_not_turned_into_none():
    """Ollama and other free models report 0.0; `or None` used to drop that."""
    fake = _embedding_response(
        [[0.1]], prompt_tokens=1, model="ollama/nomic-embed-text"
    )
    with patch("litellm.aembedding", new=AsyncMock(return_value=fake)):
        emb = LiteLLMEmbedding(model="ollama/nomic-embed-text")
        result = await emb.aembed(["x"])

    assert result.metrics.total_cost == 0.0


@pytest.mark.asyncio
async def test_azure_custom_deployment_priced_with_base_model():
    fake = _embedding_response(
        [[0.1]], prompt_tokens=3, model="azure/my-custom-deployment"
    )
    with patch("litellm.aembedding", new=AsyncMock(return_value=fake)) as mock:
        emb = LiteLLMEmbedding(
            model="azure/my-custom-deployment",
            base_model="azure/text-embedding-3-small",
            api_key="sk-test",
        )
        result = await emb.aembed(["x"])

    assert "base_model" not in mock.call_args.kwargs
    assert result.metrics.total_cost is not None and result.metrics.total_cost > 0


@pytest.mark.asyncio
async def test_unmapped_model_reports_none_cost():
    fake = _embedding_response(
        [[0.1]], prompt_tokens=3, model="azure/my-custom-deployment"
    )
    with patch("litellm.aembedding", new=AsyncMock(return_value=fake)):
        emb = LiteLLMEmbedding(model="azure/my-custom-deployment")
        result = await emb.aembed(["x"])

    assert result.metrics.total_cost is None


def test_extract_metrics_zero_from_completion_cost():
    emb = LiteLLMEmbedding(model="ollama/nomic-embed-text")
    fake = _embedding_response(
        [[0.1, 0.2]], prompt_tokens=1, model="ollama/nomic-embed-text"
    )
    metrics = emb._extract_metrics(fake, latency=0.01, vector_count=1)
    assert metrics.total_cost == 0.0
