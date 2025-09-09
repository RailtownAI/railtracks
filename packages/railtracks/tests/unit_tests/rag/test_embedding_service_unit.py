import pytest
from railtracks.rag.embedding_service import BaseEmbeddingService, EmbeddingService


@pytest.fixture(autouse=True)
def patch_litellm(monkeypatch):
    class DummyLitellm:
        @staticmethod
        def embedding(model, input, **kwargs):
            return {"data":[
                {"index":i, "embedding":[float(len(t)), 1.0, 2.0]} for i,t in enumerate(input)
            ]}

    # Patch where it is used:
    import railtracks.rag.embedding_service as embmod
    monkeypatch.setattr(embmod, "litellm", DummyLitellm)

def test_repr_includes_class_and_model():
    es = EmbeddingService(model="test-model")
    assert "EmbeddingService" in repr(es)
    assert "test-model" in repr(es)

def test_embedding_service_embed_batch_and_order():
    es = EmbeddingService(model="whatever")
    batch = ["cat", "dog"]
    vecs = es._embed_batch(batch)
    for v in vecs:
        assert v == [3.0, 1.0, 2.0]
    assert len(vecs) == 2

def test_embedding_service_embed_multiple_batches():
    es = EmbeddingService(model="foo")
    texts = ["one", "two", "three", "four"]
    out = es.embed(texts, batch_size=2)
    assert len(out) == len(texts)
    assert out[0] == [3.0, 1.0, 2.0]
    assert out[2] == [5.0, 1.0, 2.0]

def test_litellm_extra_kwargs():
    es = EmbeddingService(model="abc", api_key="XXX", base_url="http://foo", timeout=20, whatever="yes")
    assert es.litellm_extra["api_key"] == "XXX"
    assert es.litellm_extra["base_url"] == "http://foo"
    assert es.litellm_extra["whatever"] == "yes"