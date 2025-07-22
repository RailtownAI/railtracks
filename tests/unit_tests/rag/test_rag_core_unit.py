import pytest

from conftest import DummyEmbeddingService, DummyTextChunkingService, DummyVectorRecord, DummyTextObject
from railtracks.RAG.rag_core import RAG, textobject_to_vectorrecords


# Patch all dependencies using monkeypatch fixture
@pytest.fixture(autouse=True)
def patch_all(monkeypatch):
    import railtracks.RAG.rag_core as ragmod
    monkeypatch.setattr(ragmod, "TextObject", DummyTextObject)
    monkeypatch.setattr(ragmod, "EmbeddingService", DummyEmbeddingService)
    monkeypatch.setattr(ragmod, "TextChunkingService", DummyTextChunkingService)

    # Dummy vector store
    def dummy_create_store(**kwargs):
        class DummyStore:
            def __init__(self): self.added = []
            def add(self, vobjects): self.added.extend(vobjects)
            def search(self, query_vec, top_k):
                class DummyResult:
                    def __init__(self, score, text): self.score = score; self.record = text
                return [DummyResult(1.0, f"chunk{i}") for i in range(top_k)]
        return DummyStore()

    # Dummy VectorRecord
    class DummyVectorRecord:
        def __init__(self, id, vector, text, metadata):
            self.id = id
            self.vector = vector
            self.text = text
            self.metadata = metadata

    # Patch all symbols in rag module at appropriate locations
    import railtracks.RAG.rag_core as ragmod
    monkeypatch.setattr(ragmod, "TextObject", DummyTextObject)
    monkeypatch.setattr(ragmod, "EmbeddingService", DummyEmbeddingService)
    monkeypatch.setattr(ragmod, "TextChunkingService", DummyTextChunkingService)
    monkeypatch.setattr(ragmod, "create_store", dummy_create_store)

    # Patch VectorRecord for textobject_to_vectorrecords
    monkeypatch.setattr(
        ragmod, "VectorRecord", DummyVectorRecord
    )
    # Also patch VectorRecord in ragmod.textobject_to_vectorrecords if needed
    ragmod.textobject_to_vectorrecords.__globals__["VectorRecord"] = DummyVectorRecord

def test_textobject_to_vectorrecords_basic():
    class DummyTextObjectForTest:
        chunked_content = ["foo", "bar"]
        embeddings = [[0.1, 0.2], [0.3, 0.4]]
        hash = "h"
        def get_metadata(self): return {"a":1}

    records = textobject_to_vectorrecords(DummyTextObjectForTest())
    assert len(records) == 2
    assert records[0].vector == [0.1,0.2]
    assert records[1].text == "bar"
    assert "chunk_index" in records[0].metadata

def test_rag_text_init_and_embed():
    rag = RAG(docs=["abcdef"], input_type="text")
    rag.text_objects[0].chunked_content = None
    rag.text_objects[0].embeddings = None

    calls = {}
    # Patch textobject_to_vectorrecords inside the method for call-counting
    orig_t2v = rag.embed_all.__globals__["textobject_to_vectorrecords"]
    def fake_t2v(obj):
        calls["called"] = True
        return [orig_t2v(obj) for _ in range(1)]
    rag.embed_all.__globals__["textobject_to_vectorrecords"] = fake_t2v
    rag.embed_all()
    assert calls.get("called")
    assert rag.vector_store.added  # Some objects were added

def test_rag_search_returns_expected():
    rag = RAG(docs=["abcdef"], input_type="text")
    rag.text_objects[0].chunked_content = ["abc", "def"]
    rag.text_objects[0].embeddings = [[1.0, 1.0], [2.0, 2.0]]
    results = rag.search("query", top_k=2)
    assert len(results) == 2
    assert hasattr(results[0], "score")
    assert hasattr(results[0], "record")

def test_rag_path_input(tmp_path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("content")
    rag = RAG(docs=[str(file_path)], input_type="path")
    assert rag.text_objects[0].path == str(file_path)

def test_rag_path_input_file_not_exist():
    with pytest.raises(ValueError):
        RAG(docs=["notfound.txt"], input_type="path")

def test_rag_bad_input_type():
    with pytest.raises(ValueError):
        RAG(docs=["abc"], input_type="BAD")