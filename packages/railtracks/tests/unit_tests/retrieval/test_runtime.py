"""Tests for RetrievalRuntime — Phase 1 contract.

The runtime is exercised against a real ``VectorStore`` backed by
``InMemoryBackend`` so write/read/delete semantics are realistic. The
embedder and loader are fakes so we can control batch boundaries and
inject failures.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from railtracks.retrieval import (
    BatchIngested,
    Document,
    DocumentFailed,
    DocumentSkipped,
    EmbeddingFailure,
    EmbeddingModelMismatchError,
    RetrievalRuntime,
)
from railtracks.retrieval.stores import StoreScope, VectorStore
from railtracks.retrieval.chunking.base import Chunker
from railtracks.retrieval.embedding.base import Embedding
from railtracks.retrieval.embedding.models import EmbeddingMetrics, TextEmbeddings
from railtracks.retrieval.loaders.base import BaseDocumentLoader
from railtracks.retrieval.loaders.sanitizing import (
    Sanitizer,
    SanitizingLoader,
)
from railtracks.retrieval.models import Chunk
from railtracks.retrieval.runtime import _content_hash
from railtracks.retrieval.stores.models import StoreEntry
from railtracks.retrieval.stores.vector.backends.in_memory import InMemoryBackend

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _ListLoader(BaseDocumentLoader):
    def __init__(self, docs: list[Document]) -> None:
        self._docs = docs

    async def astream(self) -> AsyncGenerator[Document, None]:
        for doc in self._docs:
            yield doc


class _OneChunkPerWordChunker(Chunker):
    """Splits content on whitespace, one chunk per word. Deterministic."""

    def chunk(self, document: Document) -> list[Chunk]:
        words = document.content.split()
        return self._make_chunks(document, words)


class _FakeEmbedder(Embedding):
    """Embedder with controllable model, per-call failure injection,
    and a tiny deterministic vector (len(text)-based)."""

    default_batch_size = 2

    def __init__(
        self,
        *,
        model: str = "fake-model-1",
        fail_on_texts: set[str] | None = None,
    ) -> None:
        self._model = model
        self._fail_on = fail_on_texts or set()
        self.calls: list[list[str]] = []

    async def aembed(self, texts: list[str]) -> TextEmbeddings:
        self.calls.append(list(texts))
        for t in texts:
            if t in self._fail_on:
                raise RuntimeError(f"forced failure on {t!r}")
        vectors = [[float(len(t)), 0.0, 0.0] for t in texts]
        return TextEmbeddings(
            vectors=vectors,
            metrics=EmbeddingMetrics(model=self._model, vector_count=len(texts)),
        )


def _store() -> VectorStore:
    return VectorStore(InMemoryBackend())


def _runtime(
    *,
    embedder: Embedding | None = None,
    store: VectorStore | None = None,
    batch_size: int | None = None,
) -> tuple[RetrievalRuntime, VectorStore, _FakeEmbedder]:
    embedder = embedder or _FakeEmbedder()
    store = store or _store()
    runtime = RetrievalRuntime(
        chunker=_OneChunkPerWordChunker(),
        embedder=embedder,
        store=store,
        batch_size=batch_size,
    )
    return runtime, store, embedder  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_ingest_yields_batchingested_per_batch():
    runtime, store, _ = _runtime()
    doc = Document(content="alpha beta gamma delta")  # 4 chunks -> 2 batches

    events = [e async for e in runtime.ingest(_ListLoader([doc]))]

    batches = [e for e in events if isinstance(e, BatchIngested)]
    assert len(batches) == 2
    assert all(e.document_id == doc.id for e in batches)


async def test_batch_index_is_per_document():
    """batch_index resets to 0 for each document instead of running globally
    across the whole ingest."""
    runtime, _, _ = _runtime()  # _FakeEmbedder batch_size=2, one chunk per word
    doc_a = Document(content="alpha beta gamma delta")  # 4 chunks -> 2 batches
    doc_b = Document(content="epsilon zeta")  # 2 chunks -> 1 batch

    events = [e async for e in runtime.ingest(_ListLoader([doc_a, doc_b]))]
    batches = [e for e in events if isinstance(e, BatchIngested)]

    a_indices = [e.batch_index for e in batches if e.document_id == doc_a.id]
    b_indices = [e.batch_index for e in batches if e.document_id == doc_b.id]

    assert a_indices == [0, 1]
    assert b_indices == [0]  # resets per document; not [2] as a global counter


async def test_ingest_writes_one_entry_per_chunk():
    runtime, store, _ = _runtime()
    doc = Document(content="alpha beta gamma")  # 3 chunks

    async for _ in runtime.ingest(_ListLoader([doc])):
        pass

    # 3 chunks -> 3 entries in the store
    found = await store.find({"document_id": str(doc.id)}, limit=10)
    assert len(found) == 3


async def test_reingest_replaces_prior_version():
    """Upsert: re-ingesting a doc replaces all its chunks atomically per-doc
    (modulo crash mid-write, which is documented)."""
    store = _store()
    doc_id = uuid4()

    runtime, _, _ = _runtime(store=store)
    doc_v1 = Document(id=doc_id, content="one two three four")  # 4 chunks
    async for _ in runtime.ingest(_ListLoader([doc_v1])):
        pass
    assert len(await store.find({"document_id": str(doc_id)}, limit=10)) == 4

    doc_v2 = Document(id=doc_id, content="only two words")  # 3 chunks
    async for _ in runtime.ingest(_ListLoader([doc_v2])):
        pass
    found = await store.find({"document_id": str(doc_id)}, limit=10)
    assert len(found) == 3
    assert {e.content for e in found} == {"only", "two", "words"}


async def test_delete_where_called_before_first_write_only():
    """delete_where fires once per doc, only after the first successful batch."""
    store = _store()
    calls: list[dict] = []

    real_delete_where = store.delete_where

    async def tracking_delete_where(filters):
        calls.append(dict(filters))
        await real_delete_where(filters)

    store.delete_where = tracking_delete_where  # type: ignore[method-assign]

    runtime, _, _ = _runtime(store=store)
    doc = Document(content="alpha beta gamma delta")
    async for _ in runtime.ingest(_ListLoader([doc])):
        pass

    assert calls == [{"document_id": str(doc.id)}]


async def test_total_failure_preserves_prior_version():
    """If every batch for a re-ingest fails, the prior version stays in the store."""
    store = _store()
    doc_id = uuid4()

    # First ingest: success
    runtime_ok, _, _ = _runtime(store=store)
    doc_v1 = Document(id=doc_id, content="keep me")
    async for _ in runtime_ok.ingest(_ListLoader([doc_v1])):
        pass
    assert len(await store.find({"document_id": str(doc_id)}, limit=10)) == 2

    # Second ingest: every batch fails -> nothing deleted, nothing written
    failing_embedder = _FakeEmbedder(fail_on_texts={"new", "content", "here"})
    runtime_fail, _, _ = _runtime(store=store, embedder=failing_embedder)
    doc_v2 = Document(id=doc_id, content="new content here")
    events = [e async for e in runtime_fail.ingest(_ListLoader([doc_v2]))]

    # All embedding failures emitted, but prior data intact
    assert any(isinstance(e, EmbeddingFailure) for e in events)
    assert any(isinstance(e, DocumentFailed) for e in events)
    found = await store.find({"document_id": str(doc_id)}, limit=10)
    assert {e.content for e in found} == {"keep", "me"}


async def test_embedding_failure_is_yielded_not_raised():
    embedder = _FakeEmbedder(fail_on_texts={"bad"})
    runtime, store, _ = _runtime(embedder=embedder)
    doc = Document(content="good bad")

    events = [e async for e in runtime.ingest(_ListLoader([doc]))]

    assert any(isinstance(e, EmbeddingFailure) for e in events)
    assert any(isinstance(e, DocumentFailed) for e in events)


async def test_documentfailed_yielded_when_any_batch_fails():
    embedder = _FakeEmbedder(fail_on_texts={"third"})
    runtime, _, _ = _runtime(embedder=embedder)
    doc = Document(content="first second third fourth")

    events = [e async for e in runtime.ingest(_ListLoader([doc]))]

    failed = [e for e in events if isinstance(e, DocumentFailed)]
    assert len(failed) == 1
    assert failed[0].document_id == doc.id
    assert len(failed[0].errors) >= 1


async def test_ingest_all_returns_correct_counts():
    runtime, _, _ = _runtime()
    docs = [
        Document(content="alpha beta gamma"),  # 3 chunks
        Document(content="delta"),  # 1 chunk
    ]

    stats = await runtime.ingest_all(_ListLoader(docs))

    assert stats.documents_loaded == 2
    assert stats.documents_failed == 0
    assert stats.chunks_created == 4
    assert stats.chunks_embedded == 4


async def test_ingest_all_counts_failures():
    embedder = _FakeEmbedder(fail_on_texts={"die"})
    runtime, _, _ = _runtime(embedder=embedder)
    docs = [
        Document(content="ok ok"),  # both succeed
        Document(content="ok die"),  # one batch fails -> doc failed
    ]

    stats = await runtime.ingest_all(_ListLoader(docs))

    assert stats.documents_loaded == 2
    assert stats.documents_failed == 1
    assert stats.batches_failed >= 1


async def test_retrieve_passes_metadata_filters():
    runtime, store, _ = _runtime()
    seen_queries = []
    real_read = store.read

    async def tracking_read(query):
        seen_queries.append(query)
        return await real_read(query)

    store.read = tracking_read  # type: ignore[method-assign]

    await runtime.ingest_all(_ListLoader([Document(content="alpha beta")]))
    await runtime.retrieve(
        "alpha", top_k=3, metadata_filters={"kind": "test"}
    )

    assert seen_queries[-1].metadata_filters == {"kind": "test"}


async def test_retrieve_passes_scope_to_store():
    """Scope passed to retrieve() is forwarded onto the StoreQuery."""
    runtime, store, _ = _runtime()
    seen_queries = []
    real_read = store.read

    async def tracking_read(query):
        seen_queries.append(query)
        return await real_read(query)

    store.read = tracking_read  # type: ignore[method-assign]

    scope = StoreScope(labels={"user_id": "alice"})
    await runtime.ingest_all(_ListLoader([Document(content="alpha")]), scope=scope)
    await runtime.retrieve("alpha", scope=scope)
    assert seen_queries[-1].scope == scope


async def test_retrieve_without_scope_searches_unscoped():
    """No scope on retrieve → no scope filter applied at the store layer."""
    runtime, store, _ = _runtime()
    seen_queries = []
    real_read = store.read

    async def tracking_read(query):
        seen_queries.append(query)
        return await real_read(query)

    store.read = tracking_read  # type: ignore[method-assign]

    await runtime.ingest_all(_ListLoader([Document(content="alpha")]))
    await runtime.retrieve("alpha")
    assert seen_queries[-1].scope is None


async def test_ingest_writes_entries_with_call_scope():
    """Scope passed to ingest() ends up on every written StoreEntry."""
    runtime, store, _ = _runtime()
    alice = StoreScope(labels={"user_id": "alice"})
    bob = StoreScope(labels={"user_id": "bob"})

    await runtime.ingest_all(
        _ListLoader([Document(content="alpha beta", source="a")]),
        scope=alice,
    )
    await runtime.ingest_all(
        _ListLoader([Document(content="gamma delta", source="b")]),
        scope=bob,
    )

    alice_entries = await store.find({"scope_user_id": "alice"}, limit=10)
    bob_entries = await store.find({"scope_user_id": "bob"}, limit=10)
    assert {e.content for e in alice_entries} == {"alpha", "beta"}
    assert {e.content for e in bob_entries} == {"gamma", "delta"}


async def test_retrieve_raises_on_model_mismatch():
    embedder_v1 = _FakeEmbedder(model="model-v1")
    runtime, store, _ = _runtime(embedder=embedder_v1)
    await runtime.ingest_all(_ListLoader([Document(content="alpha beta")]))

    # Swap embedder under the runtime to simulate model drift
    runtime._embedder = _FakeEmbedder(model="model-v2")  # type: ignore[attr-defined]

    with pytest.raises(EmbeddingModelMismatchError):
        await runtime.retrieve("alpha")


async def test_fresh_runtime_catches_cross_process_model_mismatch():
    """The model guard survives process restarts: a brand-new runtime
    pointed at an existing store seeds ``_captured_model`` from any
    entry on disk, so a mismatched embedder is caught at the next
    ingest or retrieve."""
    store = _store()

    # "Process 1": writes with model-v1.
    runtime_v1, _, _ = _runtime(store=store, embedder=_FakeEmbedder(model="model-v1"))
    await runtime_v1.ingest_all(_ListLoader([Document(content="alpha beta")]))
    assert len(await store.find({}, limit=10)) == 2

    # "Process 2": fresh runtime, different embedder, same store.
    runtime_v2, _, _ = _runtime(store=store, embedder=_FakeEmbedder(model="model-v2"))

    with pytest.raises(EmbeddingModelMismatchError):
        await runtime_v2.retrieve("alpha")

    with pytest.raises(EmbeddingModelMismatchError):
        await runtime_v2.ingest_all(_ListLoader([Document(content="gamma delta")]))

    # Mismatch must abort before any writes — store still holds only
    # the two model-v1 chunks.
    assert len(await store.find({}, limit=10)) == 2


async def test_document_id_is_deterministic_from_source():
    """Same source → same id; different sources → different ids;
    sourceless → random ids; explicit id wins."""
    d1 = Document(source="docs/handbook.md", content="anything")
    d2 = Document(source="docs/handbook.md", content="different content")
    d3 = Document(source="docs/onboarding.txt", content="anything")
    d4 = Document(content="no source")
    d5 = Document(content="no source either")
    explicit = uuid4()
    d6 = Document(id=explicit, source="docs/handbook.md", content="anything")

    assert d1.id == d2.id, "same source must derive the same id"
    assert d1.id != d3.id, "different sources must derive different ids"
    assert d4.id != d5.id, "sourceless documents must get random ids"
    assert d6.id == explicit, "explicit id must override derivation"


async def test_reingest_with_default_id_replaces_prior_version():
    """The realistic loader case: callers don't set Document.id by hand.
    Same source must yield the same derived id so the runtime's
    delete_where finds and clears the prior chunks. Without the
    deterministic-id fix this test would find both versions and fail."""
    store = _store()
    runtime, _, _ = _runtime(store=store)

    doc_v1 = Document(source="docs/handbook.md", content="one two three four")
    async for _ in runtime.ingest(_ListLoader([doc_v1])):
        pass

    doc_v2 = Document(source="docs/handbook.md", content="only two words")
    assert doc_v2.id == doc_v1.id
    async for _ in runtime.ingest(_ListLoader([doc_v2])):
        pass

    chunks = await store.find({"source_path": "docs/handbook.md"}, limit=20)
    assert len(chunks) == 3, "prior version's chunks should be replaced, not retained"
    assert {e.content for e in chunks} == {"only", "two", "words"}


async def test_runtime_exposes_public_properties():
    embedder = _FakeEmbedder()
    store = _store()
    runtime = RetrievalRuntime(
        chunker=_OneChunkPerWordChunker(),
        embedder=embedder,
        store=store,
        batch_size=3,
    )

    assert runtime.store is store
    assert runtime.embedder is embedder
    assert isinstance(runtime.chunker, _OneChunkPerWordChunker)
    assert runtime.batch_size == 3
    assert runtime.max_tokens is None


async def test_init_raises_without_batch_size():
    class _NoDefaultEmbedder(_FakeEmbedder):
        default_batch_size = None

    with pytest.raises(ValueError, match="default_batch_size"):
        RetrievalRuntime(
            chunker=_OneChunkPerWordChunker(),
            embedder=_NoDefaultEmbedder(),
            store=_store(),
        )


async def test_content_hash_overwrites_loader_value():
    runtime, _, _ = _runtime()

    class _CapturingLoader(BaseDocumentLoader):
        def __init__(self, doc: Document) -> None:
            self.doc = doc

        async def astream(self) -> AsyncGenerator[Document, None]:
            yield self.doc

    doc = Document(content="payload", content_hash="bogus-hash-from-loader")
    loader = _CapturingLoader(doc)
    async for _ in runtime.ingest(loader):
        pass

    assert doc.content_hash is not None
    assert doc.content_hash != "bogus-hash-from-loader"
    assert len(doc.content_hash) == 64  # sha256 hex


async def test_retrieve_returns_chunks_ranked():
    runtime, _, _ = _runtime()
    docs = [
        Document(content="alpha beta gamma"),
        Document(content="delta epsilon"),
    ]
    await runtime.ingest_all(_ListLoader(docs))

    result = await runtime.retrieve("alpha", top_k=3)
    assert result.query == "alpha"
    assert len(result.chunks) > 0
    # ranks are sequential from 0
    assert [c.rank for c in result.chunks] == list(range(len(result.chunks)))


# ---------------------------------------------------------------------------
# Phase 4a — Staleness detection
# ---------------------------------------------------------------------------


async def test_unchanged_document_is_skipped_on_reingest():
    store = _store()
    runtime, _, _ = _runtime(store=store)
    doc = Document(source="path/to/doc", content="alpha beta gamma")

    # First ingest writes chunks
    stats1 = await runtime.ingest_all(_ListLoader([doc]))
    assert stats1.documents_skipped == 0
    assert stats1.chunks_embedded == 3

    # Re-ingest of *same* content yields DocumentSkipped, no new embedding work
    runtime2, _, embedder2 = _runtime(store=store)
    doc_again = Document(
        source="path/to/doc", content="alpha beta gamma"
    )  # same content -> same hash
    events = [e async for e in runtime2.ingest(_ListLoader([doc_again]))]

    assert any(isinstance(e, DocumentSkipped) for e in events)
    assert embedder2.calls == []  # never embedded


async def test_changed_document_is_reembedded():
    store = _store()
    runtime, _, _ = _runtime(store=store)
    doc_v1 = Document(source="path/to/doc", content="alpha beta")
    await runtime.ingest_all(_ListLoader([doc_v1]))

    # Different content -> different hash -> not skipped
    doc_v2 = Document(source="path/to/doc", content="completely different text now")
    events = [e async for e in runtime.ingest(_ListLoader([doc_v2]))]

    assert not any(isinstance(e, DocumentSkipped) for e in events)
    assert any(isinstance(e, BatchIngested) for e in events)


async def test_partial_document_is_reingested_not_skipped():
    """Count-aware staleness: if a prior ingest left only some of a document's
    chunks in the store, the next run must NOT skip it — it must re-ingest and
    end up complete. Simulates a partial write by deleting one chunk."""
    store = _store()
    runtime, _, _ = _runtime(store=store)
    doc = Document(source="path/to/doc", content="alpha beta gamma")  # 3 chunks

    await runtime.ingest_all(_ListLoader([doc]))
    entries = await store.find({"source_path": "path/to/doc"}, limit=10)
    assert len(entries) == 3
    assert entries[0].chunk_metadata["doc_chunk_count"] == 3

    # Simulate an interrupted ingest: drop one chunk so the store is partial.
    await store.delete(entries[0].id)
    assert await store.count({"source_path": "path/to/doc"}) == 2

    # Re-ingest the *same* content. Old find()-only logic would skip (an entry
    # still exists). Count-aware logic sees 2 < 3 and re-ingests.
    runtime2, _, embedder2 = _runtime(store=store)
    same = Document(source="path/to/doc", content="alpha beta gamma")
    events = [e async for e in runtime2.ingest(_ListLoader([same]))]

    assert not any(isinstance(e, DocumentSkipped) for e in events)
    assert embedder2.calls, "partial document should have been re-embedded"
    # And it ends up complete again — exactly 3 chunks, no duplicates.
    assert await store.count({"source_path": "path/to/doc"}) == 3


async def test_complete_document_with_count_metadata_is_skipped():
    """A fully-written document (have == doc_chunk_count) still skips."""
    store = _store()
    runtime, _, _ = _runtime(store=store)
    doc = Document(source="path/to/doc", content="alpha beta gamma")

    await runtime.ingest_all(_ListLoader([doc]))

    runtime2, _, embedder2 = _runtime(store=store)
    same = Document(source="path/to/doc", content="alpha beta gamma")
    events = [e async for e in runtime2.ingest(_ListLoader([same]))]

    assert any(isinstance(e, DocumentSkipped) for e in events)
    assert embedder2.calls == []


async def test_entry_without_count_metadata_is_reingested():
    """Every chunk the runtime writes carries doc_chunk_count, so an entry
    without it was written by something else — its completeness can't be
    verified and the document must be re-ingested, not skipped."""
    store = _store()

    # Hand-write an entry with source_path + content_hash but no
    # doc_chunk_count in metadata.
    runtime, _, _ = _runtime(store=store)
    content = "alpha beta gamma"
    doc = Document(source="path/to/doc", content=content)
    chunk_hash = _content_hash(content)

    foreign = StoreEntry(
        id=uuid4(),
        content="alpha",
        vector=[1.0, 0.0, 0.0],
        # Matches _FakeEmbedder so the model-consistency guard (which seeds
        # itself from existing entries) doesn't trip before the re-ingest.
        embedding_model="fake-model-1",
        chunk_id=uuid4(),
        document_id=doc.id,
        chunk_metadata={"source_path": "path/to/doc", "content_hash": chunk_hash},
    )
    await store.write(foreign)

    runtime2, _, embedder2 = _runtime(store=store)
    events = [e async for e in runtime2.ingest(_ListLoader([doc]))]

    assert not any(isinstance(e, DocumentSkipped) for e in events)
    assert embedder2.calls, "unverifiable document should have been re-embedded"
    # Re-ingest replaced the unstamped entry with properly stamped chunks.
    entries = await store.find({"source_path": "path/to/doc"}, limit=10)
    assert entries and all(
        e.chunk_metadata.get("doc_chunk_count") == 3 for e in entries
    )


async def test_skip_requires_source():
    """Documents without `source` cannot be staleness-checked and always re-ingest."""
    store = _store()
    runtime, _, embedder = _runtime(store=store)
    doc1 = Document(content="alpha beta")  # source=None
    doc2 = Document(content="alpha beta")  # source=None, same content
    await runtime.ingest_all(_ListLoader([doc1]))
    embedder_call_count = len(embedder.calls)
    await runtime.ingest_all(_ListLoader([doc2]))
    assert len(embedder.calls) > embedder_call_count


async def test_reingest_never_issues_large_limit_find():
    """Regression for the Chroma Cloud quota bug (#1180): the old duplicate
    check called find(limit=doc_chunk_count), and Chroma Cloud rejects any
    get whose limit exceeds its per-request quota (300). The presence check
    must instead go through count(), so find() is only ever called with
    limit=1 no matter how many chunks a document has."""
    store = _store()
    seed_runtime, _, _ = _runtime(store=store)
    # 400 chunks (one per word) — would have produced find(limit=400) before.
    content = " ".join(f"word{i}" for i in range(400))
    doc = Document(source="big/doc", content=content)
    await seed_runtime.ingest_all(_ListLoader([doc]))

    find_limits: list[int] = []
    original_find = store.find

    async def spying_find(filters, limit=1):
        find_limits.append(limit)
        return await original_find(filters, limit=limit)

    store.find = spying_find  # type: ignore[method-assign]

    runtime2, _, embedder2 = _runtime(store=store)
    same = Document(source="big/doc", content=content)
    stats = await runtime2.ingest_all(_ListLoader([same]))

    assert stats.documents_skipped == 1
    assert embedder2.calls == []
    assert find_limits, "duplicate check should have consulted the store"
    assert max(find_limits) == 1


# ---------------------------------------------------------------------------
# Phase 4b — Audit hooks
# ---------------------------------------------------------------------------


async def test_on_ingest_hook_is_called():
    seen: list = []
    runtime = RetrievalRuntime(
        chunker=_OneChunkPerWordChunker(),
        embedder=_FakeEmbedder(),
        store=_store(),
        on_ingest=seen.append,
    )
    await runtime.ingest_all(_ListLoader([Document(content="alpha beta")]))
    assert any(isinstance(e, BatchIngested) for e in seen)


async def test_on_retrieve_hook_is_called():
    seen: list = []
    runtime = RetrievalRuntime(
        chunker=_OneChunkPerWordChunker(),
        embedder=_FakeEmbedder(),
        store=_store(),
        on_retrieve=lambda q, r: seen.append((q, r)),
    )
    await runtime.ingest_all(_ListLoader([Document(content="alpha beta")]))
    result = await runtime.retrieve("alpha")
    assert seen == [("alpha", result)]


# ---------------------------------------------------------------------------
# Phase 4c — Token-size guard
# ---------------------------------------------------------------------------


class _FakeTokenizer:
    """Token count = number of words. Lets us write fast deterministic tests."""

    def encode(self, text: str) -> list[int]:
        return list(range(len(text.split())))

    def decode(self, tokens):
        raise NotImplementedError

    def count(self, text: str) -> int:
        return len(text.split())


async def test_max_tokens_drops_oversized_chunks():
    runtime = RetrievalRuntime(
        chunker=_OneChunkPerWordChunker(),
        embedder=_FakeEmbedder(),
        store=_store(),
        max_tokens=1,
        tokenizer=_FakeTokenizer(),
    )
    # _OneChunkPerWordChunker emits 1 token per chunk → all fit under max_tokens=1
    stats = await runtime.ingest_all(_ListLoader([Document(content="alpha beta")]))
    assert stats.batches_failed == 0
    assert stats.chunks_embedded == 2


async def test_max_tokens_oversized_chunk_yields_embedding_failure():
    class _BigWordChunker(Chunker):
        """One chunk per *whole* document — content stays large."""

        def chunk(self, document: Document) -> list[Chunk]:
            if not document.content:
                return []
            return self._make_chunks(document, [document.content])

    runtime = RetrievalRuntime(
        chunker=_BigWordChunker(),
        embedder=_FakeEmbedder(),
        store=_store(),
        max_tokens=2,
        tokenizer=_FakeTokenizer(),
    )

    doc = Document(content="alpha beta gamma")  # 3 words -> 3 tokens > 2
    events = [e async for e in runtime.ingest(_ListLoader([doc]))]

    failures = [e for e in events if isinstance(e, EmbeddingFailure)]
    assert len(failures) == 1
    assert "tokens" in str(failures[0].errors[0])
    # No batch ever sent to the embedder because the only chunk was dropped
    assert not any(isinstance(e, BatchIngested) for e in events)
    assert any(isinstance(e, DocumentFailed) for e in events)


# ---------------------------------------------------------------------------
# Phase 5 — Sanitizing loader
# ---------------------------------------------------------------------------


class _UpperSanitizer:
    """Rewrites Document.content to upper-case."""

    def sanitize(self, document: Document) -> Document:
        document.content = document.content.upper()
        return document


async def test_sanitizing_loader_yields_sanitized_documents():
    inner = _ListLoader([Document(content="hello world")])
    sanitizing = SanitizingLoader(inner, _UpperSanitizer())

    docs = [doc async for doc in sanitizing.astream()]
    assert len(docs) == 1
    assert docs[0].content == "HELLO WORLD"


async def test_sanitizing_loader_sanitizer_protocol():
    assert isinstance(_UpperSanitizer(), Sanitizer)


async def test_sanitizer_errors_propagate():
    class _Boom:
        def sanitize(self, document: Document) -> Document:
            raise RuntimeError("redaction failure")

    inner = _ListLoader([Document(content="x")])
    loader = SanitizingLoader(inner, _Boom())
    with pytest.raises(RuntimeError, match="redaction failure"):
        [_ async for _ in loader.astream()]
