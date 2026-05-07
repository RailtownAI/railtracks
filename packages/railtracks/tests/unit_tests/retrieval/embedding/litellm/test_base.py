from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from railtracks.retrieval.embedding import EmbeddingMetrics, LiteLLMEmbedding, TextEmbeddings


def _fake_response(
    vectors: list[list[float]],
    prompt_tokens: int = 10,
    response_cost: float = 0.0001,
    model: str = "openai/text-embedding-3-small",
) -> SimpleNamespace:
    data = [SimpleNamespace(embedding=v) for v in vectors]
    usage = SimpleNamespace(prompt_tokens=prompt_tokens)
    resp = SimpleNamespace(data=data, usage=usage, model=model)
    resp._hidden_params = {"response_cost": response_cost}
    return resp


@pytest.mark.asyncio
async def test_aembed_returns_text_embeddings():
    fake = _fake_response([[0.1, 0.2], [0.3, 0.4]])
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
    fake = _fake_response([[0.1, 0.2]], prompt_tokens=7, response_cost=0.0005)
    with patch("litellm.aembedding", new=AsyncMock(return_value=fake)):
        emb = LiteLLMEmbedding(model="openai/text-embedding-3-small")
        result = await emb.aembed(["hello"])

    m = result.metrics
    assert m.input_tokens == 7
    assert m.total_cost == pytest.approx(0.0005)
    assert m.latency is not None and m.latency >= 0
    assert m.vector_count == 1
    assert m.dimension == 2


@pytest.mark.asyncio
async def test_aembed_metrics_graceful_when_fields_missing():
    bare = SimpleNamespace(data=[SimpleNamespace(embedding=[0.1])], model=None)
    bare._hidden_params = {}
    with patch("litellm.aembedding", new=AsyncMock(return_value=bare)):
        emb = LiteLLMEmbedding(model="openai/text-embedding-3-small")
        result = await emb.aembed(["x"])

    assert result.metrics.input_tokens is None
    assert result.metrics.total_cost is None
