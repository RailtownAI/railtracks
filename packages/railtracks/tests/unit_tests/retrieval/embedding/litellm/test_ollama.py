from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from railtracks.retrieval.embedding import OllamaEmbedding


def _fake_response(vectors: list[list[float]]) -> SimpleNamespace:
    data = [SimpleNamespace(embedding=v) for v in vectors]
    resp = SimpleNamespace(data=data, usage=SimpleNamespace(prompt_tokens=1), model="ollama/nomic-embed-text")
    resp._hidden_params = {"response_cost": 0.0}
    return resp


def test_ollama_embedding_default_model():
    emb = OllamaEmbedding()
    assert emb._model == "ollama/nomic-embed-text"


def test_ollama_embedding_default_batch_size():
    assert OllamaEmbedding.default_batch_size == 1


@pytest.mark.asyncio
async def test_ollama_embedding_uses_ollama_prefix():
    with patch("litellm.aembedding", new=AsyncMock(return_value=_fake_response([[0.1]]))) as mock:
        emb = OllamaEmbedding()
        await emb.aembed(["x"])
    assert mock.call_args.kwargs["model"].startswith("ollama/")


@pytest.mark.asyncio
async def test_ollama_embedding_passes_api_base():
    with patch("litellm.aembedding", new=AsyncMock(return_value=_fake_response([[0.1]]))) as mock:
        emb = OllamaEmbedding(api_base="http://myhost:11434")
        await emb.aembed(["x"])
    assert mock.call_args.kwargs["api_base"] == "http://myhost:11434"
