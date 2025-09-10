import pytest

from typing import List, Sequence, Optional, Any, Dict
from dataclasses import dataclass

# Import the RAG implementation under test
from railtracks.rag.rag_core import RAG, RAGConfig, textobject_to_vectorrecords
from railtracks.rag.text_object import TextObject
from railtracks.rag.vector_store.base import VectorRecord


# ----------------------------- Dummy services ----------------------------- #

class DummyEmbedService:
    """
    Minimal embedding service for tests.
    - For a list[str], returns [[len(s), len(s)]] vectors to keep it obvious and 2D.
    - For a list[list[float]], returns as-is (not used by RAG but safe).
    """
    def __init__(self, **kwargs):
        self.calls: List[Sequence[str]] = []

    def embed(self, inputs: Sequence[str]) -> List[List[float]]:
        self.calls.append(inputs)
        out = []
        for x in inputs:
            if isinstance(x, str):
                L = float(len(x))
                out.append([L, L])
            else:
                # Not expected for RAG path, but keep it pass-through-safe.
                out.append(x)
        return out


class DummyStore:
    """
    Minimal vector store capturing calls and received records/queries.
    """
    def __init__(self, **kwargs):
        self.add_calls: int = 0
        self.received_records: List[VectorRecord] = []
        self.search_calls: int = 0
        self.last_query: Optional[List[float]] = None
        self.last_top_k: Optional[int] = None

    def add(self, records: Sequence[VectorRecord]):
        self.add_calls += 1
        self.received_records.extend(records)
        # No return value needed

    def search(self, query: List[float], top_k: int = 5):
        self.search_calls += 1
        self.last_query = query
        self.last_top_k = top_k
        # Return a minimal object that behaves like a SearchResult (iterable)
        class DummyResult(list):
            pass
        return DummyResult()


class DummyChunker:
    """
    Chunker returning a fixed split for predictable behavior.
    """
    def __init__(self, chunks: Optional[List[str]] = None):
        self._chunks = chunks or ["A", "BB", "CCC"]
        self.calls: int = 0

    def chunk(self, text: str) -> List[str]:
        self.calls += 1
        return list(self._chunks)


# ----------------------------- Tests ----------------------------- #

def test_rag_uses_service_overrides_not_create_store(monkeypatch):
    # Patch create_store to error if called; service override should avoid calling it.
    called = {"create_store_called": False}
    def fake_create_store(**kwargs):
        called["create_store_called"] = True
        raise AssertionError("create_store should not be called when vector_store override is provided")

    monkeypatch.setattr("railtracks.rag.rag_core.create_store", fake_create_store)

    embed = DummyEmbedService()
    store = DummyStore()
    chunker = DummyChunker(chunks=["a", "b"])

    rag = RAG(
        docs=["doc1"],
        embedding_service=embed,
        vector_store=store,
        chunk_service=chunker,
    )

    rag.embed_all()

    # Ensure overrides used, and create_store was never called.
    assert not called["create_store_called"]
    assert store.add_calls == 1
    assert len(store.received_records) == len(chunker._chunks)
    # Type and id format sanity for received records
    for i, rec in enumerate(store.received_records):
        assert isinstance(rec, VectorRecord)
        assert rec.id.endswith(f"-{i}")


def test_embed_all_produces_vectorrecords_and_ids_are_deterministic():
    # Use overrides so no external services are constructed.
    embed = DummyEmbedService()
    store = DummyStore()
    chunker = DummyChunker(chunks=["x", "yy", "zzz"])
    rag = RAG(docs=["abcdef"], embedding_service=embed, vector_store=store, chunk_service=chunker)

    # Capture the expected resource hash to check deterministic ids
    tobj = rag.text_objects[0]
    expected_hash = tobj.hash

    rag.embed_all()

    assert store.add_calls == 1
    assert len(store.received_records) == 3

    for i, rec in enumerate(store.received_records):
        # Deterministic id: "{hash}-{i}"
        assert rec.id == f"{expected_hash}-{i}"
        # Vector length should be 2 (from DummyEmbedService)
        assert isinstance(rec.vector, list) and len(rec.vector) == 2
        # Metadata should contain chunk info
        assert rec.metadata["chunk_index"] == i
        assert rec.metadata["chunk"] == chunker._chunks[i]
        # Text should be the chunk content
        assert rec.text == chunker._chunks[i]


def test_textobject_to_vectorrecords_min_length_used():
    # Create a TextObject and manually set chunked_content and embeddings of different lengths
    tobj = TextObject("rawdoc")
    tobj.set_chunked(["c1", "c2", "c3"])
    tobj.set_embeddings([[1.0], [2.0]])  # fewer embeddings than chunks

    records = textobject_to_vectorrecords(tobj)
    # Should take min length: 2
    assert len(records) == 2
    assert records[0].metadata["chunk"] == "c1"
    assert records[1].metadata["chunk"] == "c2"


def test_search_text_embeds_then_search_uses_vector_and_topk():
    embed = DummyEmbedService()
    store = DummyStore()
    chunker = DummyChunker(chunks=["a"])
    rag = RAG(docs=["doc"], embedding_service=embed, vector_store=store, chunk_service=chunker)

    res = rag.search("query", top_k=7)
    assert store.search_calls == 1
    # Embedding called with ["query"]
    assert embed.calls and list(embed.calls[-1]) == ["query"]
    # Store received the vector, not the raw string
    assert isinstance(store.last_query, list) and all(isinstance(x, float) for x in store.last_query)
    assert store.last_top_k == 7
    # Result is iterable (empty, by our DummyStore)
    assert hasattr(res, "__iter__")


def test_search_vector_bypasses_embedding():
    embed = DummyEmbedService()
    store = DummyStore()
    chunker = DummyChunker(chunks=["a"])
    rag = RAG(docs=["doc"], embedding_service=embed, vector_store=store, chunk_service=chunker)

    q_vec = [0.1, 0.2]
    res = rag.search(q_vec, top_k=2)
    assert store.search_calls == 1
    assert store.last_query == q_vec
    # Embedding service should not be called for vector queries
    assert embed.calls == []
    assert store.last_top_k == 2
    assert hasattr(res, "__iter__")


def test_add_docs_appends_to_text_objects():
    rag = RAG(docs=["d1", "d2"], embedding_service=DummyEmbedService(), vector_store=DummyStore(), chunk_service=DummyChunker())
    assert len(rag.text_objects) == 2
    rag.add_docs(["d3", "d4", "d5"])
    assert len(rag.text_objects) == 5
    assert [t.raw_content for t in rag.text_objects[-3:]] == ["d3", "d4", "d5"]


def test_config_chunk_strategy_is_used(monkeypatch):
    # Provide a custom chunking strategy via RAGConfig and ensure it's used by the constructed TextChunkingService
    def my_strategy(self, text: str) -> List[str]:
        return [text[:2], text[2:5]]

    cfg = RAGConfig(chunk_strategy=my_strategy)
    embed = DummyEmbedService()
    store = DummyStore()
    # No chunk_service override here: we test that RAG uses cfg.chunk_strategy
    rag = RAG(docs=["abcdefgh"], config=cfg, embedding_service=embed, vector_store=store)

    rag.embed_all()

    # Our strategy produces 2 chunks; so 2 records should be added
    assert len(store.received_records) == 2
    assert [rec.text for rec in store.received_records] == ["ab", "cde"]


def test_embed_all_with_no_docs_no_store_calls():
    rag = RAG(docs=[], embedding_service=DummyEmbedService(), vector_store=DummyStore(), chunk_service=DummyChunker())
    rag.embed_all()
    assert rag.vector_store.add_calls == 0