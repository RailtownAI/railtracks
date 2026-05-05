from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from railtracks.retrieval.embedding import AzureEmbedding


def _fake_response(vectors: list[list[float]]) -> SimpleNamespace:
    data = [SimpleNamespace(embedding=v) for v in vectors]
    resp = SimpleNamespace(data=data, usage=SimpleNamespace(prompt_tokens=1), model="azure/my-deploy")
    resp._hidden_params = {"response_cost": 0.0001}
    return resp


@pytest.mark.asyncio
async def test_azure_embedding_passes_connection_params():
    with patch("litellm.aembedding", new=AsyncMock(return_value=_fake_response([[0.1]]))) as mock:
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
