from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from litellm.types.utils import EmbeddingResponse, Usage
from railtracks.retrieval.embedding import OllamaEmbedding


def _fake_response(vectors: list[list[float]]) -> EmbeddingResponse:
    data = [
        {"embedding": v, "index": i, "object": "embedding"}
        for i, v in enumerate(vectors)
    ]
    return EmbeddingResponse(
        model="ollama/nomic-embed-text",
        data=data,
        usage=Usage(prompt_tokens=1, total_tokens=1),
    )


def test_ollama_embedding_default_model():
    emb = OllamaEmbedding()
    assert emb._model == "ollama/nomic-embed-text"


def test_ollama_embedding_default_batch_size():
    assert OllamaEmbedding.default_batch_size == 1


@pytest.mark.asyncio
async def test_ollama_embedding_uses_ollama_prefix():
    with patch(
        "litellm.aembedding", new=AsyncMock(return_value=_fake_response([[0.1]]))
    ) as mock:
        emb = OllamaEmbedding()
        await emb.aembed(["x"])
    assert mock.call_args.kwargs["model"].startswith("ollama/")


@pytest.mark.asyncio
async def test_ollama_embedding_passes_api_base():
    with patch(
        "litellm.aembedding", new=AsyncMock(return_value=_fake_response([[0.1]]))
    ) as mock:
        emb = OllamaEmbedding(api_base="http://myhost:11434")
        await emb.aembed(["x"])
    assert mock.call_args.kwargs["api_base"] == "http://myhost:11434"


@pytest.mark.asyncio
async def test_ollama_embedding_reports_zero_cost():
    with patch(
        "litellm.aembedding", new=AsyncMock(return_value=_fake_response([[0.1]]))
    ):
        emb = OllamaEmbedding()
        result = await emb.aembed(["x"])
    assert result.metrics.total_cost == 0.0
