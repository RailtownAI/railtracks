from collections.abc import AsyncGenerator

import pytest
from railtracks.retrieval.loaders.base import BaseDocumentLoader
from railtracks.retrieval.loaders.models import LoadFailure
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

    @pytest.mark.asyncio
    async def test_load_works_from_running_event_loop(self):
        """Calling sync load() from inside a running event loop must not raise.

        Previously this raised "asyncio.run() cannot be called from a running
        event loop" — fatal in Jupyter and async test contexts. The fix
        offloads execution to a worker thread when a loop is already running.
        """
        docs = [_make_doc("x"), _make_doc("y")]
        loader = ConcreteLoader(docs)
        result = loader.load()
        assert result == docs


class _FailingSourceLoader(BaseDocumentLoader):
    """Reads three sources; the middle one yields one document then raises."""

    def __init__(self) -> None:
        self.closed = False

    async def _read(self, name: str) -> AsyncGenerator[Document, None]:
        yield _make_doc(f"{name}-1")
        if name == "bad":
            raise OSError("disk read failed")
        yield _make_doc(f"{name}-2")

    async def astream(self) -> AsyncGenerator[Document | LoadFailure, None]:
        try:
            for name in ("first", "bad", "last"):
                async for item in self._isolate_source(name, self._read(name)):
                    yield item
        finally:
            self.closed = True


class TestSourceIsolation:
    """Tests for _isolate_source and how aload/load treat LoadFailure."""

    async def test_failing_source_yields_load_failure_and_stream_continues(self):
        items = [item async for item in _FailingSourceLoader().astream()]

        contents = [i.content for i in items if isinstance(i, Document)]
        failures = [i for i in items if isinstance(i, LoadFailure)]
        assert contents == ["first-1", "first-2", "bad-1", "last-1", "last-2"]
        assert len(failures) == 1
        assert failures[0].source == "bad"
        assert isinstance(failures[0].error, OSError)

    async def test_aload_raises_first_load_failure_error(self):
        loader = _FailingSourceLoader()

        with pytest.raises(OSError, match="disk read failed"):
            await loader.aload()
        assert loader.closed

    def test_load_raises_first_load_failure_error(self):
        with pytest.raises(OSError, match="disk read failed"):
            _FailingSourceLoader().load()
