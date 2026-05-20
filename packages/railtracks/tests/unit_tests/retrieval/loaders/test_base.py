from collections.abc import AsyncGenerator

import pytest
from railtracks.retrieval.loaders.base import BaseDocumentLoader
from railtracks.retrieval.models import Document, DocumentType


class ConcreteLoader(BaseDocumentLoader):
    """Minimal concrete loader that yields a fixed list of documents."""

    def __init__(self, docs: list[Document]) -> None:
        self._docs = docs

    async def astream(self) -> AsyncGenerator[Document, None]:
        for doc in self._docs:
            yield doc


def _make_doc(content: str = "hello") -> Document:
    return Document(content=content, type=DocumentType.TEXT)


class TestBaseDocumentLoaderAbstract:
    """Tests verifying the abstract contract of BaseDocumentLoader."""

    def test_cannot_instantiate_without_astream(self):
        """Instantiating BaseDocumentLoader directly raises TypeError."""
        with pytest.raises(TypeError):
            BaseDocumentLoader()  # type: ignore[abstract]

    def test_concrete_subclass_missing_astream_raises(self):
        """A subclass that does not implement astream cannot be instantiated."""
        class Incomplete(BaseDocumentLoader):
            pass

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore[abstract]

    def test_concrete_subclass_with_astream_instantiates(self):
        """A subclass that implements astream can be instantiated."""
        loader = ConcreteLoader([])
        assert isinstance(loader, BaseDocumentLoader)


class TestBaseDocumentLoaderAload:
    """Tests for the aload() convenience method."""

    async def test_aload_returns_all_documents(self):
        """aload() collects every document yielded by astream()."""
        docs = [_make_doc("a"), _make_doc("b"), _make_doc("c")]
        loader = ConcreteLoader(docs)
        result = await loader.aload()
        assert result == docs

    async def test_aload_empty_stream_returns_empty_list(self):
        """aload() returns an empty list when astream() yields nothing."""
        loader = ConcreteLoader([])
        result = await loader.aload()
        assert result == []

    async def test_aload_preserves_order(self):
        """aload() preserves the yield order from astream()."""
        docs = [_make_doc(str(i)) for i in range(10)]
        loader = ConcreteLoader(docs)
        result = await loader.aload()
        assert [d.content for d in result] == [str(i) for i in range(10)]


class TestBaseDocumentLoaderLoad:
    """Tests for the synchronous load() wrapper."""

    def test_load_returns_all_documents(self):
        """load() collects every document yielded by astream()."""
        docs = [_make_doc("x"), _make_doc("y")]
        loader = ConcreteLoader(docs)
        result = loader.load()
        assert result == docs

    def test_load_empty_stream_returns_empty_list(self):
        """load() returns an empty list when astream() yields nothing."""
        loader = ConcreteLoader([])
        result = loader.load()
        assert result == []
