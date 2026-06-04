from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from railtracks.retrieval.embedding import OpenAIEmbedding


def _fake_response(vectors: list[list[float]]) -> SimpleNamespace:
    data = [SimpleNamespace(embedding=v) for v in vectors]
    resp = SimpleNamespace(data=data, usage=SimpleNamespace(prompt_tokens=1), model="openai/text-embedding-3-small")
    resp._hidden_params = {"response_cost": 0.0001}
    return resp


@pytest.mark.asyncio
async def test_openai_embedding_uses_openai_prefix():
    with patch("litellm.aembedding", new=AsyncMock(return_value=_fake_response([[0.1]]))) as mock:
        emb = OpenAIEmbedding()
        await emb.aembed(["x"])
    assert mock.call_args.kwargs["model"].startswith("openai/")


def test_openai_embedding_default_model():
    emb = OpenAIEmbedding()
    assert emb._model == "openai/text-embedding-3-small"


@pytest.mark.asyncio
async def test_openai_embedding_dimensions_forwarded():
    with patch("litellm.aembedding", new=AsyncMock(return_value=_fake_response([[0.1]]))) as mock:
        emb = OpenAIEmbedding(dimensions=256)
        await emb.aembed(["x"])
    assert mock.call_args.kwargs["dimensions"] == 256


def test_openai_embedding_no_dimensions_by_default():
    emb = OpenAIEmbedding()
    assert "dimensions" not in emb._kwargs
