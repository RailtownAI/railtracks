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
    SyncEmbedding,
    TextEmbeddings,
)
from railtracks.retrieval.models import Chunk, EmbeddedChunk


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


# ---------------------------------------------------------------------------
# astream_batches — basic behaviour
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
        results = [r async for r in emb.astream_batches(chunks, batch_size=10)]
    assert len(results) == 1


@pytest.mark.asyncio
async def test_astream_batches_accepts_async_iterable():
    async def chunk_stream():
        for c in [_chunk("a"), _chunk("b"), _chunk("c")]:
            yield c

    fake = _fake_response([[0.1, 0.2]] * 3)
    with patch("litellm.aembedding", new=AsyncMock(return_value=fake)):
        emb = LiteLLMEmbedding(model="openai/text-embedding-3-small")
        results = [r async for r in emb.astream_batches(chunk_stream(), batch_size=10)]
    assert len(results) == 1
    assert isinstance(results[0], EmbeddingResult)


# ---------------------------------------------------------------------------
# astream_batches — default_batch_size guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_astream_batches_raises_when_no_batch_size():
    class NoBatchSizeEmb(Embedding):
        async def aembed(self, texts):
            return TextEmbeddings(vectors=[[0.1]] * len(texts), metrics=EmbeddingMetrics())

    emb = NoBatchSizeEmb()
    with pytest.raises(ValueError, match="default_batch_size"):
        async for _ in emb.astream_batches([_chunk("a")]):
            pass


# ---------------------------------------------------------------------------
# astream_batches — vector count mismatch guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_astream_batches_failure_on_vector_count_mismatch():
    chunks = [_chunk("a"), _chunk("b")]
    # provider returns only 1 vector for 2 inputs
    fake = _fake_response([[0.1, 0.2]])
    with patch("litellm.aembedding", new=AsyncMock(return_value=fake)):
        emb = LiteLLMEmbedding(model="openai/text-embedding-3-small")
        results = [r async for r in emb.astream_batches(chunks, batch_size=10)]
    assert len(results) == 1
    assert isinstance(results[0], EmbeddingFailure)
    assert len(results[0].errors) == 1


# ---------------------------------------------------------------------------
# astream_batches — concurrency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_astream_batches_concurrency_yields_in_order():
    chunks = [_chunk(f"c{i}") for i in range(4)]
    call_order: list[int] = []

    async def fake_aembedding(model, input, **kwargs):
        call_order.append(len(input))
        return _fake_response([[float(i)] * 2 for i in range(len(input))])

    with patch("litellm.aembedding", side_effect=fake_aembedding):
        emb = LiteLLMEmbedding(model="openai/text-embedding-3-small")
        results = [
            r async for r in emb.astream_batches(chunks, batch_size=2, concurrency=2)
        ]

    assert len(results) == 2
    assert all(isinstance(r, EmbeddingResult) for r in results)
    # chunks from both batches should be present and in original order
    all_chunks = [ec.chunk for r in results for ec in r.chunks]
    assert [c.content for c in all_chunks] == [f"c{i}" for i in range(4)]


# ---------------------------------------------------------------------------
# Sync guards
# ---------------------------------------------------------------------------


def test_embed_works_in_sync_context():
    fake = _fake_response([[0.1, 0.2]])
    with patch("litellm.aembedding", new=AsyncMock(return_value=fake)):
        emb = LiteLLMEmbedding(model="openai/text-embedding-3-small")
        result = emb.embed(["hello"])
    assert isinstance(result, TextEmbeddings)
    assert result.vectors == [[0.1, 0.2]]


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
