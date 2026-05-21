from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from railtracks.retrieval.loaders.pdf_ocr_loader import PyPDFOCRLoader
from railtracks.retrieval.models import DocumentType


def _make_reader(page_texts: list[str]) -> MagicMock:
    """Build a mock pypdf.PdfReader whose pages return the given texts."""
    reader = MagicMock()
    pages = []
    for text in page_texts:
        page = MagicMock()
        page.extract_text.return_value = text
        pages.append(page)
    reader.pages = pages
    return reader


def _make_pdfium(page_count: int) -> MagicMock:
    """Build a mock pypdfium2.PdfDocument with `page_count` pages.

    Each page's `.render(...).to_pil()` returns a sentinel image object so
    we can verify it makes it into pytesseract.image_to_string.
    """
    pdf = MagicMock()
    pages = []
    for i in range(page_count):
        page = MagicMock()
        bitmap = MagicMock()
        bitmap.to_pil.return_value = f"<image-page-{i + 1}>"
        page.render.return_value = bitmap
        pages.append(page)
    pdf.__getitem__.side_effect = lambda i: pages[i]
    pdf.__len__.return_value = page_count
    return pdf


def _patch_pdf_backends(reader_mock: MagicMock, pdfium_mock: MagicMock):
    """Patch both PDF backends used by PyPDFOCRLoader at once."""
    return (
        patch(
            "railtracks.retrieval.loaders.pdf_ocr_loader.PdfReader",
            return_value=reader_mock,
        ),
        patch(
            "railtracks.retrieval.loaders.pdf_ocr_loader.pdfium.PdfDocument",
            return_value=pdfium_mock,
        ),
    )


class TestPyPDFOCRLoaderInit:
    """Tests for PyPDFOCRLoader construction."""

    def test_invalid_breakdown_strategy_raises_value_error(self, tmp_path):
        with pytest.raises(ValueError, match="breakdown_strategy"):
            PyPDFOCRLoader(
                str(tmp_path / "x.pdf"),
                breakdown_strategy="chapters",  # type: ignore[arg-type]
            )

    def test_non_positive_dpi_raises_value_error(self, tmp_path):
        with pytest.raises(ValueError, match="dpi"):
            PyPDFOCRLoader(str(tmp_path / "x.pdf"), dpi=0)
        with pytest.raises(ValueError, match="dpi"):
            PyPDFOCRLoader(str(tmp_path / "x.pdf"), dpi=-10)

    def test_default_strategy_is_page(self, tmp_path):
        loader = PyPDFOCRLoader(str(tmp_path / "x.pdf"))
        assert loader._breakdown_strategy == "page"

    def test_force_ocr_defaults_to_false(self, tmp_path):
        loader = PyPDFOCRLoader(str(tmp_path / "x.pdf"))
        assert loader._force_ocr is False

    def test_dpi_default_is_300(self, tmp_path):
        loader = PyPDFOCRLoader(str(tmp_path / "x.pdf"))
        assert loader._dpi == 300

    def test_language_default_is_eng(self, tmp_path):
        loader = PyPDFOCRLoader(str(tmp_path / "x.pdf"))
        assert loader._language == "eng"


class TestPyPDFOCRLoaderErrors:
    """Tests for file-access error conditions."""

    async def test_missing_file_raises_file_not_found(self, tmp_path):
        loader = PyPDFOCRLoader(str(tmp_path / "ghost.pdf"))
        with pytest.raises(FileNotFoundError):
            await loader.aload()

    async def test_unsupported_extension_raises_value_error(self, tmp_path):
        f = tmp_path / "data.txt"
        f.write_text("not a pdf", encoding="utf-8")
        loader = PyPDFOCRLoader(str(f))
        with pytest.raises(ValueError, match="PyPDFOCRLoader expects a .pdf file"):
            await loader.aload()


class TestPyPDFOCRLoaderTextLayer:
    """Pages with an embedded text layer should NOT trigger OCR (the fast path)."""

    async def test_text_layer_used_when_present(self, tmp_path):
        """If pypdf returns text, pytesseract should never be called."""
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        reader = _make_reader(["embedded text"])
        pdfium = _make_pdfium(page_count=1)

        reader_patch, pdfium_patch = _patch_pdf_backends(reader, pdfium)
        with (
            reader_patch,
            pdfium_patch,
            patch(
                "railtracks.retrieval.loaders.pdf_ocr_loader.pytesseract.image_to_string"
            ) as mock_ocr,
        ):
            docs = await PyPDFOCRLoader(str(pdf)).aload()

        assert len(docs) == 1
        assert docs[0].content == "embedded text"
        assert docs[0].metadata["ocr"] is False
        mock_ocr.assert_not_called()

    async def test_document_type_is_pdf(self, tmp_path):
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        reader = _make_reader(["content"])
        pdfium = _make_pdfium(page_count=1)
        reader_patch, pdfium_patch = _patch_pdf_backends(reader, pdfium)
        with reader_patch, pdfium_patch:
            docs = await PyPDFOCRLoader(str(pdf)).aload()
        assert docs[0].type == DocumentType.PDF


class TestPyPDFOCRLoaderOCRFallback:
    """Pages with an empty text layer should trigger OCR (the fallback path)."""

    async def test_ocr_used_when_text_layer_empty(self, tmp_path):
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        reader = _make_reader([""])  # page exists but has no text
        pdfium = _make_pdfium(page_count=1)

        reader_patch, pdfium_patch = _patch_pdf_backends(reader, pdfium)
        with (
            reader_patch,
            pdfium_patch,
            patch(
                "railtracks.retrieval.loaders.pdf_ocr_loader.pytesseract.image_to_string",
                return_value="ocr extracted text",
            ) as mock_ocr,
        ):
            docs = await PyPDFOCRLoader(str(pdf)).aload()

        assert len(docs) == 1
        assert docs[0].content == "ocr extracted text"
        assert docs[0].metadata["ocr"] is True
        mock_ocr.assert_called_once()

    async def test_ocr_used_for_whitespace_only_text_layer(self, tmp_path):
        """Pages where extract_text returns only whitespace also fall back to OCR."""
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        reader = _make_reader(["   \n  "])
        pdfium = _make_pdfium(page_count=1)

        reader_patch, pdfium_patch = _patch_pdf_backends(reader, pdfium)
        with (
            reader_patch,
            pdfium_patch,
            patch(
                "railtracks.retrieval.loaders.pdf_ocr_loader.pytesseract.image_to_string",
                return_value="scanned content",
            ),
        ):
            docs = await PyPDFOCRLoader(str(pdf)).aload()

        assert docs[0].content == "scanned content"
        assert docs[0].metadata["ocr"] is True

    async def test_mixed_pdf_uses_text_for_some_ocr_for_others(self, tmp_path):
        """A PDF with both text and scanned pages should use the right path per page."""
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        reader = _make_reader(["page 1 text", "", "page 3 text"])
        pdfium = _make_pdfium(page_count=3)

        reader_patch, pdfium_patch = _patch_pdf_backends(reader, pdfium)
        with (
            reader_patch,
            pdfium_patch,
            patch(
                "railtracks.retrieval.loaders.pdf_ocr_loader.pytesseract.image_to_string",
                return_value="page 2 ocr",
            ),
        ):
            docs = await PyPDFOCRLoader(str(pdf)).aload()

        assert len(docs) == 3
        assert docs[0].content == "page 1 text"
        assert docs[0].metadata["ocr"] is False
        assert docs[1].content == "page 2 ocr"
        assert docs[1].metadata["ocr"] is True
        assert docs[2].content == "page 3 text"
        assert docs[2].metadata["ocr"] is False

    async def test_ocr_uses_configured_language(self, tmp_path):
        """The language constructor argument is passed through to pytesseract."""
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        reader = _make_reader([""])
        pdfium = _make_pdfium(page_count=1)

        reader_patch, pdfium_patch = _patch_pdf_backends(reader, pdfium)
        with (
            reader_patch,
            pdfium_patch,
            patch(
                "railtracks.retrieval.loaders.pdf_ocr_loader.pytesseract.image_to_string",
                return_value="ja text",
            ) as mock_ocr,
        ):
            await PyPDFOCRLoader(str(pdf), language="jpn").aload()

        _, kwargs = mock_ocr.call_args
        assert kwargs["lang"] == "jpn"


class TestPyPDFOCRLoaderForceOCR:
    """`force_ocr=True` should OCR every page without checking the text layer."""

    async def test_force_ocr_skips_text_extraction(self, tmp_path):
        """Even pages with a text layer should be OCR'd when force_ocr=True."""
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        reader = _make_reader(["embedded text that should be ignored"])
        pdfium = _make_pdfium(page_count=1)

        reader_patch, pdfium_patch = _patch_pdf_backends(reader, pdfium)
        with (
            reader_patch,
            pdfium_patch,
            patch(
                "railtracks.retrieval.loaders.pdf_ocr_loader.pytesseract.image_to_string",
                return_value="forced ocr text",
            ) as mock_ocr,
        ):
            docs = await PyPDFOCRLoader(str(pdf), force_ocr=True).aload()

        assert docs[0].content == "forced ocr text"
        assert docs[0].metadata["ocr"] is True
        mock_ocr.assert_called_once()
        # extract_text on the page should not have been consulted
        reader.pages[0].extract_text.assert_not_called()


class TestPyPDFOCRLoaderPageStrategy:
    """The 'page' strategy yields one Document per non-empty page."""

    async def test_metadata_includes_page_and_totals(self, tmp_path):
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        reader = _make_reader(["a", "b", "c"])
        pdfium = _make_pdfium(page_count=3)
        reader_patch, pdfium_patch = _patch_pdf_backends(reader, pdfium)
        with reader_patch, pdfium_patch:
            docs = await PyPDFOCRLoader(str(pdf)).aload()
        assert [d.metadata["page"] for d in docs] == [1, 2, 3]
        assert all(d.metadata["total_pages"] == 3 for d in docs)
        assert all(d.metadata["file_type"] == ".pdf" for d in docs)

    async def test_pages_empty_after_both_paths_are_skipped(self, tmp_path):
        """If text layer is empty AND OCR returns nothing, the page is skipped."""
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        reader = _make_reader(["", ""])
        pdfium = _make_pdfium(page_count=2)
        reader_patch, pdfium_patch = _patch_pdf_backends(reader, pdfium)
        with (
            reader_patch,
            pdfium_patch,
            patch(
                "railtracks.retrieval.loaders.pdf_ocr_loader.pytesseract.image_to_string",
                return_value="",
            ),
        ):
            docs = await PyPDFOCRLoader(str(pdf)).aload()
        assert docs == []


class TestPyPDFOCRLoaderDocumentStrategy:
    """The 'document' strategy yields one Document per file."""

    async def test_yields_one_document_per_file(self, tmp_path):
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        reader = _make_reader(["one", "two"])
        pdfium = _make_pdfium(page_count=2)
        reader_patch, pdfium_patch = _patch_pdf_backends(reader, pdfium)
        with reader_patch, pdfium_patch:
            docs = await PyPDFOCRLoader(str(pdf), breakdown_strategy="document").aload()
        assert len(docs) == 1

    async def test_pages_joined_with_double_newline(self, tmp_path):
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        reader = _make_reader(["first", "second"])
        pdfium = _make_pdfium(page_count=2)
        reader_patch, pdfium_patch = _patch_pdf_backends(reader, pdfium)
        with reader_patch, pdfium_patch:
            docs = await PyPDFOCRLoader(str(pdf), breakdown_strategy="document").aload()
        assert docs[0].content == "first\n\nsecond"

    async def test_ocr_pages_metadata_records_which_pages_used_ocr(self, tmp_path):
        """In document strategy, ocr_pages lists 1-based pages that needed OCR."""
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        reader = _make_reader(["text", "", "text", ""])
        pdfium = _make_pdfium(page_count=4)
        reader_patch, pdfium_patch = _patch_pdf_backends(reader, pdfium)
        with (
            reader_patch,
            pdfium_patch,
            patch(
                "railtracks.retrieval.loaders.pdf_ocr_loader.pytesseract.image_to_string",
                return_value="ocr",
            ),
        ):
            docs = await PyPDFOCRLoader(str(pdf), breakdown_strategy="document").aload()
        assert docs[0].metadata["ocr_pages"] == [2, 4]

    async def test_empty_pages_excluded_from_concatenated_document(self, tmp_path):
        """Empty pages must not leave double-newline gaps in the joined output.

        Mirrors the page-strategy behaviour where empty pages are skipped, so
        a 3-page PDF with an empty middle page reads as `"p1\\n\\np3"`, not
        `"p1\\n\\n\\n\\np3"`.
        """
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        reader = _make_reader(["page 1 text", "", "page 3 text"])
        pdfium = _make_pdfium(page_count=3)
        reader_patch, pdfium_patch = _patch_pdf_backends(reader, pdfium)
        with (
            reader_patch,
            pdfium_patch,
            patch(
                "railtracks.retrieval.loaders.pdf_ocr_loader.pytesseract.image_to_string",
                return_value="",
            ),
        ):
            docs = await PyPDFOCRLoader(str(pdf), breakdown_strategy="document").aload()
        assert docs[0].content == "page 1 text\n\npage 3 text"


class TestPyPDFOCRLoaderDirectory:
    """Directory loading mirrors PyPDFLoader: sorted, .pdf-only, recursive."""

    async def test_directory_loads_all_pdf_files(self, tmp_path):
        (tmp_path / "a.pdf").touch()
        (tmp_path / "b.pdf").touch()
        reader = _make_reader(["content"])
        pdfium = _make_pdfium(page_count=1)
        reader_patch, pdfium_patch = _patch_pdf_backends(reader, pdfium)
        with reader_patch, pdfium_patch:
            docs = await PyPDFOCRLoader(
                str(tmp_path), breakdown_strategy="document"
            ).aload()
        assert len(docs) == 2

    async def test_empty_directory_returns_empty_list(self, tmp_path):
        docs = await PyPDFOCRLoader(str(tmp_path)).aload()
        assert docs == []

    async def test_directory_ignores_non_pdf_files(self, tmp_path):
        (tmp_path / "doc.pdf").touch()
        (tmp_path / "readme.txt").write_text("text", encoding="utf-8")
        reader = _make_reader(["pdf content"])
        pdfium = _make_pdfium(page_count=1)
        reader_patch, pdfium_patch = _patch_pdf_backends(reader, pdfium)
        with reader_patch, pdfium_patch:
            docs = await PyPDFOCRLoader(
                str(tmp_path), breakdown_strategy="document"
            ).aload()
        assert len(docs) == 1
