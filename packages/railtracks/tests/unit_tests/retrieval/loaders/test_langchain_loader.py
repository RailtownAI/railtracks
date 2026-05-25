from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import pytest
from railtracks.retrieval.loaders.langchain_loader import LangChainLoaderAdapter
from railtracks.retrieval.models import DocumentType


@dataclass
class FakeLCDocument:
    """Minimal stand-in for ``langchain_core.documents.Document``."""

    page_content: str
    metadata: dict = field(default_factory=dict)


class _AsyncLoader:
    """LangChain-style loader exposing alazy_load (preferred path)."""

    def __init__(self, docs: list[FakeLCDocument]) -> None:
        self._docs = docs
        self.alazy_load_called = False
        self.lazy_load_called = False
        self.load_called = False

    async def alazy_load(self):
        self.alazy_load_called = True
        for d in self._docs:
            yield d

    def lazy_load(self):
        self.lazy_load_called = True
        yield from self._docs

    def load(self) -> list[FakeLCDocument]:
        self.load_called = True
        return list(self._docs)


class _LazyOnlyLoader:
    """LangChain-style loader exposing only lazy_load (middle path)."""

    def __init__(self, docs: list[FakeLCDocument]) -> None:
        self._docs = docs
        self.yielded_count = 0
        self.consumed_after_each_yield: list[int] = []

    def lazy_load(self):
        for d in self._docs:
            self.yielded_count += 1
            yield d


class _EagerOnlyLoader:
    """LangChain-style loader exposing only load (fallback path)."""

    def __init__(self, docs: list[FakeLCDocument]) -> None:
        self._docs = docs
        self.load_called = False

    def load(self) -> list[FakeLCDocument]:
        self.load_called = True
        return list(self._docs)


class _UselessLoader:
    """Loader that doesn't implement any of the LangChain methods."""


class TestConversion:
    async def test_page_content_preserved(self):
        loader = _AsyncLoader([FakeLCDocument(page_content="hello world")])
        docs = await LangChainLoaderAdapter(loader).aload()
        assert docs[0].content == "hello world"

    async def test_metadata_source_is_popped_into_document_source(self):
        loader = _AsyncLoader(
            [
                FakeLCDocument(
                    page_content="x", metadata={"source": "s3://bucket/key", "page": 1}
                )
            ]
        )
        docs = await LangChainLoaderAdapter(loader).aload()
        assert docs[0].source == "s3://bucket/key"
        assert "source" not in docs[0].metadata
        assert docs[0].metadata == {"page": 1}

    async def test_explicit_source_overrides_metadata_source(self):
        loader = _AsyncLoader(
            [
                FakeLCDocument(
                    page_content="x", metadata={"source": "ignored", "page": 1}
                )
            ]
        )
        docs = await LangChainLoaderAdapter(loader, source="override").aload()
        assert docs[0].source == "override"
        assert docs[0].metadata == {"source": "ignored", "page": 1}

    async def test_default_document_type_is_text(self):
        loader = _AsyncLoader([FakeLCDocument(page_content="x")])
        docs = await LangChainLoaderAdapter(loader).aload()
        assert docs[0].type == DocumentType.TEXT

    async def test_document_type_applied_to_every_document(self):
        loader = _AsyncLoader(
            [
                FakeLCDocument(page_content="a"),
                FakeLCDocument(page_content="b"),
            ]
        )
        docs = await LangChainLoaderAdapter(
            loader, document_type=DocumentType.MARKDOWN
        ).aload()
        assert [d.type for d in docs] == [DocumentType.MARKDOWN, DocumentType.MARKDOWN]

    async def test_missing_metadata_yields_empty_dict_and_none_source(self):
        loader = _AsyncLoader([FakeLCDocument(page_content="x", metadata={})])
        docs = await LangChainLoaderAdapter(loader).aload()
        assert docs[0].source is None
        assert docs[0].metadata == {}

    async def test_metadata_is_shallow_copied(self):
        """Mutating Document.metadata must not bleed back into the LC doc."""
        original_metadata: dict[str, Any] = {"page": 1}
        lc_doc = FakeLCDocument(page_content="x", metadata=original_metadata)
        loader = _AsyncLoader([lc_doc])
        docs = await LangChainLoaderAdapter(loader).aload()
        docs[0].metadata["page"] = 999
        assert original_metadata == {"page": 1}


class TestStreamingPriority:
    async def test_alazy_load_is_used_when_available(self):
        loader = _AsyncLoader([FakeLCDocument(page_content="x")])
        await LangChainLoaderAdapter(loader).aload()
        assert loader.alazy_load_called is True
        assert loader.lazy_load_called is False
        assert loader.load_called is False

    async def test_lazy_load_used_when_no_alazy_load(self):
        """The adapter must consume lazy_load when alazy_load is absent."""
        loader = _LazyOnlyLoader(
            [FakeLCDocument(page_content=f"d{i}") for i in range(3)]
        )
        docs = await LangChainLoaderAdapter(loader).aload()
        assert [d.content for d in docs] == ["d0", "d1", "d2"]
        assert loader.yielded_count == 3

    async def test_lazy_load_is_streamed_one_at_a_time(self):
        """Verify items are pulled lazily — the adapter must not buffer the
        full corpus before yielding the first document downstream."""
        loader = _LazyOnlyLoader(
            [FakeLCDocument(page_content=f"d{i}") for i in range(5)]
        )
        observed_counts: list[int] = []
        async for doc in LangChainLoaderAdapter(loader).astream():
            observed_counts.append(loader.yielded_count)
            assert doc.content.startswith("d")
        assert observed_counts == [1, 2, 3, 4, 5]

    async def test_load_used_as_fallback(self):
        loader = _EagerOnlyLoader(
            [
                FakeLCDocument(page_content="a"),
                FakeLCDocument(page_content="b"),
            ]
        )
        docs = await LangChainLoaderAdapter(loader).aload()
        assert loader.load_called is True
        assert [d.content for d in docs] == ["a", "b"]


class TestErrors:
    def test_loader_missing_all_methods_raises_type_error(self):
        with pytest.raises(TypeError, match="LangChain BaseLoader interface"):
            LangChainLoaderAdapter(_UselessLoader())


class TestSyncWrapper:
    def test_load_returns_same_documents_as_aload(self):
        docs_in = [FakeLCDocument(page_content="a"), FakeLCDocument(page_content="b")]
        sync_docs = LangChainLoaderAdapter(_AsyncLoader(docs_in)).load()
        async_docs = asyncio.run(LangChainLoaderAdapter(_AsyncLoader(docs_in)).aload())
        assert (
            [d.content for d in sync_docs]
            == [d.content for d in async_docs]
            == ["a", "b"]
        )
