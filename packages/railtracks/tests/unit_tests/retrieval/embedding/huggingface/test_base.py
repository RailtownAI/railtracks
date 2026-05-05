from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from railtracks.retrieval.embedding import HuggingFaceEmbedding


@pytest.mark.asyncio
async def test_huggingface_embedding_aembed():
    import numpy as np

    fake_output = np.array([[0.1, 0.2]])
    model = "sentence-transformers/all-MiniLM-L6-v2"

    with patch(
        "railtracks.retrieval.embedding.huggingface.base.AsyncInferenceClient.feature_extraction",
        new=AsyncMock(return_value=fake_output),
    ) as mock_fe:
        emb = HuggingFaceEmbedding(model=model)
        result = await emb.aembed(["hello"])

    assert mock_fe.call_args.kwargs["model"] == model
    assert result.vectors[0] == pytest.approx([0.1, 0.2])
    assert result.metrics.model == model


@pytest.mark.asyncio
async def test_huggingface_embedding_custom_provider():
    import numpy as np

    with patch(
        "railtracks.retrieval.embedding.huggingface.base.AsyncInferenceClient",
    ) as mock_cls:
        instance = MagicMock()
        instance.feature_extraction = AsyncMock(return_value=np.array([[0.1]]))
        mock_cls.return_value = instance
        emb = HuggingFaceEmbedding(
            model="sentence-transformers/all-MiniLM-L6-v2",
            provider="together",
        )
        await emb.aembed(["x"])

    assert mock_cls.call_args.kwargs["provider"] == "together"
