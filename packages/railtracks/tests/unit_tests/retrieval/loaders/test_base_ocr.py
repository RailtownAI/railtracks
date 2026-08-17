from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from railtracks.retrieval.loaders.base_ocr import BaseOCRLoader
from railtracks.retrieval.models import Document, DocumentType


class _StubOCRLoader(BaseOCRLoader):
    """Minimal concrete subclass for exercising BaseOCRLoader's contract.

    Doesn't actually OCR — it pretends `_ocr_image` always returns a fixed
    string, and `astream` synthesises one Document per fake "image" so we
    can verify the inherited `aload()` / `load()` paths still work.
    """

    def __init__(self, fake_pages: int, ocr_output: str = "ocr text") -> None:
        self._fake_pages = fake_pages
        self._ocr_output = ocr_output

    async def _ocr_image(self, image) -> str:
        return self._ocr_output

    async def astream(self) -> AsyncGenerator[Document, None]:
        for i in range(self._fake_pages):
            text = await self._ocr_image(object())  # opaque stand-in for Image
            yield Document(
                content=text,
                type=DocumentType.PDF,
                source="stub",
                metadata={"page": i + 1},
            )


class TestBaseOCRLoaderContract:
    """The abstract surface BaseOCRLoader exposes to subclasses."""

    def test_cannot_be_instantiated_directly(self):
        """BaseOCRLoader has an abstract method, so it can't be constructed."""
        with pytest.raises(TypeError):
            BaseOCRLoader()  # type: ignore[abstract]

    def test_subclass_must_implement_ocr_image(self):
        """A subclass that doesn't override `_ocr_image` is still abstract."""

        class Incomplete(BaseOCRLoader):
            async def astream(self):
                yield  # type: ignore[misc]

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore[abstract]


class TestBaseOCRLoaderInheritance:
    """The base provides aload/load via BaseDocumentLoader; verify they work."""

    async def test_ocr_image_is_called(self):
        """_ocr_image is the hook subclasses implement."""
        loader = _StubOCRLoader(fake_pages=1, ocr_output="hello")
        docs = await loader.aload()
        assert docs[0].content == "hello"

    async def test_aload_collects_all_documents(self):
        """The inherited aload() drains astream() into a list."""
        loader = _StubOCRLoader(fake_pages=3)
        docs = await loader.aload()
        assert len(docs) == 3
        assert all(isinstance(d, Document) for d in docs)

    def test_load_runs_synchronously(self):
        """The inherited load() is a blocking wrapper around aload()."""
        loader = _StubOCRLoader(fake_pages=2)
        docs = loader.load()
        assert len(docs) == 2

    async def test_empty_stream_yields_no_documents(self):
        """A subclass that emits nothing produces an empty result."""
        loader = _StubOCRLoader(fake_pages=0)
        docs = await loader.aload()
        assert docs == []
