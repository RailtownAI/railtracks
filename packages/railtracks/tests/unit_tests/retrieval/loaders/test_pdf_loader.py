from unittest.mock import MagicMock, patch

import pytest
from railtracks.retrieval.loaders.pdf_loader import PyPDFLoader
from railtracks.retrieval.models import DocumentType


def _make_reader(page_texts: list[str]) -> MagicMock:
    """Build a mock PdfReader with pages that return the given texts."""
    reader = MagicMock()
    pages = []
    for text in page_texts:
        page = MagicMock()
        page.extract_text.return_value = text
        pages.append(page)
    reader.pages = pages
    return reader


class TestPyPDFLoaderInit:
    """Tests for PyPDFLoader construction."""

    def test_invalid_breakdown_strategy_raises_value_error(self, tmp_path):
        """An unrecognised breakdown_strategy raises ValueError at construction."""
        with pytest.raises(ValueError, match="breakdown_strategy"):
            PyPDFLoader(str(tmp_path / "x.pdf"), breakdown_strategy="chapters")  # type: ignore[arg-type]

    def test_valid_page_strategy_accepted(self, tmp_path):
        """'page' is a valid breakdown_strategy."""
        loader = PyPDFLoader(str(tmp_path / "x.pdf"), breakdown_strategy="page")
        assert loader._breakdown_strategy == "page"

    def test_valid_document_strategy_accepted(self, tmp_path):
        """'document' is a valid breakdown_strategy."""
        loader = PyPDFLoader(str(tmp_path / "x.pdf"), breakdown_strategy="document")
        assert loader._breakdown_strategy == "document"

    def test_default_strategy_is_page(self, tmp_path):
        """The default breakdown_strategy is 'page'."""
        loader = PyPDFLoader(str(tmp_path / "x.pdf"))
        assert loader._breakdown_strategy == "page"


class TestPyPDFLoaderErrors:
    """Tests for file-access error conditions."""

    async def test_missing_file_raises_file_not_found(self, tmp_path):
        """A path to a nonexistent file raises FileNotFoundError."""
        loader = PyPDFLoader(str(tmp_path / "ghost.pdf"))
        with pytest.raises(FileNotFoundError):
            await loader.aload()

    async def test_unsupported_extension_raises_value_error(self, tmp_path):
        """A file with a non-.pdf extension raises ValueError."""
        f = tmp_path / "data.txt"
        f.write_text("not a pdf", encoding="utf-8")
        loader = PyPDFLoader(str(f))
        with pytest.raises(ValueError, match="PyPDFLoader expects a .pdf file"):
            await loader.aload()


class TestPyPDFLoaderPageStrategy:
    """Tests for the 'page' breakdown strategy."""

    async def test_yields_one_document_per_non_empty_page(self, tmp_path):
        """One Document is produced for each non-empty page."""
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        reader = _make_reader(["Page one text", "Page two text"])
        with patch("railtracks.retrieval.loaders.pdf_loader.PdfReader", return_value=reader):
            docs = await PyPDFLoader(str(pdf), breakdown_strategy="page").aload()
        assert len(docs) == 2

    async def test_empty_pages_are_skipped(self, tmp_path):
        """Pages with no text content are not yielded."""
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        reader = _make_reader(["First page", "", "   ", "Last page"])
        with patch("railtracks.retrieval.loaders.pdf_loader.PdfReader", return_value=reader):
            docs = await PyPDFLoader(str(pdf), breakdown_strategy="page").aload()
        assert len(docs) == 2
        assert docs[0].content == "First page"
        assert docs[1].content == "Last page"
        assert docs[0].metadata["page"] == 1
        assert docs[1].metadata["page"] == 4

    async def test_page_number_in_metadata(self, tmp_path):
        """metadata['page'] is the 1-based page number."""
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        reader = _make_reader(["p1", "p2"])
        with patch("railtracks.retrieval.loaders.pdf_loader.PdfReader", return_value=reader):
            docs = await PyPDFLoader(str(pdf), breakdown_strategy="page").aload()
        assert docs[0].metadata["page"] == 1
        assert docs[1].metadata["page"] == 2

    async def test_total_pages_in_metadata(self, tmp_path):
        """metadata['total_pages'] reflects the total page count of the PDF."""
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        reader = _make_reader(["p1", "p2", "p3"])
        with patch("railtracks.retrieval.loaders.pdf_loader.PdfReader", return_value=reader):
            docs = await PyPDFLoader(str(pdf), breakdown_strategy="page").aload()
        assert all(d.metadata["total_pages"] == 3 for d in docs)

    async def test_document_type_is_pdf(self, tmp_path):
        """Document type is PDF."""
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        reader = _make_reader(["content"])
        with patch("railtracks.retrieval.loaders.pdf_loader.PdfReader", return_value=reader):
            docs = await PyPDFLoader(str(pdf), breakdown_strategy="page").aload()
        assert docs[0].type == DocumentType.PDF

    async def test_all_pages_empty_yields_nothing(self, tmp_path):
        """A PDF where every page is empty yields no Documents."""
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        reader = _make_reader(["", "   "])
        with patch("railtracks.retrieval.loaders.pdf_loader.PdfReader", return_value=reader):
            docs = await PyPDFLoader(str(pdf), breakdown_strategy="page").aload()
        assert docs == []


class TestPyPDFLoaderDocumentStrategy:
    """Tests for the 'document' breakdown strategy."""

    async def test_yields_one_document_for_entire_pdf(self, tmp_path):
        """The 'document' strategy produces exactly one Document per file."""
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        reader = _make_reader(["page 1", "page 2", "page 3"])
        with patch("railtracks.retrieval.loaders.pdf_loader.PdfReader", return_value=reader):
            docs = await PyPDFLoader(str(pdf), breakdown_strategy="document").aload()
        assert len(docs) == 1

    async def test_pages_joined_with_double_newline(self, tmp_path):
        """Pages are joined with '\\n\\n' in the document strategy."""
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        reader = _make_reader(["first", "second"])
        with patch("railtracks.retrieval.loaders.pdf_loader.PdfReader", return_value=reader):
            docs = await PyPDFLoader(str(pdf), breakdown_strategy="document").aload()
        assert docs[0].content == "first\n\nsecond"

    async def test_total_pages_in_metadata(self, tmp_path):
        """metadata['total_pages'] reflects the total page count."""
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        reader = _make_reader(["a", "b"])
        with patch("railtracks.retrieval.loaders.pdf_loader.PdfReader", return_value=reader):
            docs = await PyPDFLoader(str(pdf), breakdown_strategy="document").aload()
        assert docs[0].metadata["total_pages"] == 2

    async def test_no_page_key_in_metadata(self, tmp_path):
        """The 'document' strategy does not include a 'page' key in metadata."""
        pdf = tmp_path / "doc.pdf"
        pdf.touch()
        reader = _make_reader(["content"])
        with patch("railtracks.retrieval.loaders.pdf_loader.PdfReader", return_value=reader):
            docs = await PyPDFLoader(str(pdf), breakdown_strategy="document").aload()
        assert "page" not in docs[0].metadata


class TestPyPDFLoaderDirectory:
    """Tests for PyPDFLoader loading a directory."""

    async def test_directory_loads_all_pdf_files(self, tmp_path):
        """All .pdf files in a directory are loaded."""
        (tmp_path / "a.pdf").touch()
        (tmp_path / "b.pdf").touch()
        reader = _make_reader(["content"])
        with patch("railtracks.retrieval.loaders.pdf_loader.PdfReader", return_value=reader):
            docs = await PyPDFLoader(str(tmp_path), breakdown_strategy="document").aload()
        assert len(docs) == 2

    async def test_empty_directory_returns_empty_list(self, tmp_path):
        """An empty directory yields no documents."""
        docs = await PyPDFLoader(str(tmp_path)).aload()
        assert docs == []

    async def test_directory_ignores_non_pdf_files(self, tmp_path):
        """Non-.pdf files in a directory are silently ignored."""
        (tmp_path / "doc.pdf").touch()
        (tmp_path / "readme.txt").write_text("text", encoding="utf-8")
        reader = _make_reader(["pdf content"])
        with patch("railtracks.retrieval.loaders.pdf_loader.PdfReader", return_value=reader):
            docs = await PyPDFLoader(str(tmp_path), breakdown_strategy="document").aload()
        assert len(docs) == 1
