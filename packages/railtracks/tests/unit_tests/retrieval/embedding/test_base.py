from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from railtracks.retrieval.embedding import (
    Embedding,
    EmbeddingFailure,
    EmbeddingMetrics,
    EmbeddingResult,
    LiteLLMEmbedding,
    MultimodalEmbedder,
    SyncEmbedding,
    TextEmbeddings,
)
from railtracks.retrieval.models import EmbeddedChunk, Chunk


def _chunk(content: str = "hello world") -> Chunk:
    return Chunk(content=content, document_id=uuid4())


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


# ---------------------------------------------------------------------------
# ABC enforcement
# ---------------------------------------------------------------------------


def test_embedding_is_abstract():
    with pytest.raises(TypeError):
        Embedding()  # type: ignore[abstract]


def test_multimodal_embedder_is_abstract():
    with pytest.raises(TypeError):
        MultimodalEmbedder()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# astream_batches
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_astream_batches_yields_results():
    chunks = [_chunk(f"c{i}") for i in range(3)]
    fake = _fake_response([[float(i)] * 2 for i in range(3)])

    with patch("litellm.aembedding", new=AsyncMock(return_value=fake)):
        emb = LiteLLMEmbedding(model="openai/text-embedding-3-small")
        results = [r async for r in emb.astream_batches(chunks, batch_size=10)]

    assert len(results) == 1
    assert isinstance(results[0], EmbeddingResult)
    assert len(results[0].chunks) == 3


@pytest.mark.asyncio
async def test_astream_batches_yields_failure_and_continues():
    chunks = [_chunk("a"), _chunk("b"), _chunk("c")]
    call_count = 0

    async def fake_aembedding(model, input, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("transient error")
        return _fake_response([[0.1] * 2 for _ in input])

    with patch("litellm.aembedding", side_effect=fake_aembedding):
        emb = LiteLLMEmbedding(model="openai/text-embedding-3-small")
        outcomes = [r async for r in emb.astream_batches(chunks, batch_size=2)]

    assert len(outcomes) == 2
    assert isinstance(outcomes[0], EmbeddingFailure)
    assert isinstance(outcomes[1], EmbeddingResult)


@pytest.mark.asyncio
async def test_astream_batches_accepts_plain_list():
    chunks = [_chunk("a"), _chunk("b")]
    fake = _fake_response([[0.1, 0.2], [0.3, 0.4]])
    with patch("litellm.aembedding", new=AsyncMock(return_value=fake)):
        emb = LiteLLMEmbedding(model="openai/text-embedding-3-small")
        results = [r async for r in emb.astream_batches(chunks)]
    assert len(results) == 1


# ---------------------------------------------------------------------------
# astream_chunks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_astream_chunks_yields_embedded_chunks():
    chunks = [_chunk("x"), _chunk("y")]
    fake = _fake_response([[1.0, 2.0], [3.0, 4.0]])
    with patch("litellm.aembedding", new=AsyncMock(return_value=fake)):
        emb = LiteLLMEmbedding(model="openai/text-embedding-3-small")
        collected = [ec async for ec in emb.astream_chunks(chunks)]
    assert len(collected) == 2
    assert all(isinstance(ec, EmbeddedChunk) for ec in collected)


@pytest.mark.asyncio
async def test_astream_chunks_raises_on_failure():
    chunks = [_chunk("a"), _chunk("b")]
    with patch("litellm.aembedding", new=AsyncMock(side_effect=RuntimeError("boom"))):
        emb = LiteLLMEmbedding(model="openai/text-embedding-3-small")
        with pytest.raises(RuntimeError, match="boom"):
            async for _ in emb.astream_chunks(chunks):
                pass


# ---------------------------------------------------------------------------
# Sync guards
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_embed_raises_in_async_context():
    emb = LiteLLMEmbedding(model="openai/text-embedding-3-small")
    with pytest.raises(RuntimeError, match="async context"):
        emb.embed(["hello"])


# ---------------------------------------------------------------------------
# SyncEmbedding mixin
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_embedding_mixin():
    class MySyncEmb(SyncEmbedding):
        def _embed_sync(self, texts):
            return TextEmbeddings(
                vectors=[[float(i)] * 2 for i in range(len(texts))],
                metrics=EmbeddingMetrics(model="sync-model"),
            )

    emb = MySyncEmb()
    result = await emb.aembed(["a", "b"])
    assert len(result.vectors) == 2
    assert result.metrics.model == "sync-model"
