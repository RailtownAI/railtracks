import pytest
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock

from railtracks.vector_stores import MediaParser

class TestMediaParser:
    """Tests for the MediaParser class."""

    def test_get_extension(self):
        """Test _get_extension method."""
        assert MediaParser._get_extension("file.txt") == ".txt"
        assert MediaParser._get_extension("file.PDF") == ".pdf"
        assert MediaParser._get_extension("/path/to/file.TXT") == ".txt"

    def test_get_extension_no_extension(self):
        """Test _get_extension with no extension."""
        assert MediaParser._get_extension("file") == ""

    def test_clean_text_removes_null_bytes(self):
        """Test _clean_text removes null bytes."""
        text = "Hello\x00World"
        cleaned = MediaParser._clean_text(text)

        assert "\x00" not in cleaned
        assert cleaned == "HelloWorld"

    def test_clean_text_preserves_whitespace(self):
        """Test _clean_text preserves normal whitespace."""
        text = "Hello\nWorld\t!\r\n"
        cleaned = MediaParser._clean_text(text)

        assert cleaned == text

    def test_clean_text_removes_non_printable(self):
        """Test _clean_text removes non-printable characters."""
        text = "Hello\x01\x02World"
        cleaned = MediaParser._clean_text(text)

        assert cleaned == "HelloWorld"

    def test_clean_text_empty_string(self):
        """Test _clean_text with empty string."""
        assert MediaParser._clean_text("") == ""

    def test_clean_text_empty(self):
        """Test _clean_text with empty string."""
        assert MediaParser._clean_text("") == ""

    def test_parse_txt_file(self):
        """Test parsing a text file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("Hello\nWorld")
            temp_path = f.name

        try:
            content = MediaParser._parse_txt(temp_path, encoding="utf-8")
            assert content == "Hello\nWorld"
        finally:
            os.unlink(temp_path)

    def test_parse_txt_file_not_found(self):
        """Test parsing non-existent text file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="File not found"):
            MediaParser._parse_txt("nonexistent.txt")

    def test_parse_txt_with_auto_detect_encoding(self):
        """Test parsing text file with auto-detected encoding."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("Test content")
            temp_path = f.name

        try:
            content = MediaParser._parse_txt(temp_path, encoding=None)
            assert content == "Test content"
        finally:
            os.unlink(temp_path)

    @patch("railtracks.vector_stores.chunking.media_parser.from_path")
    def test_parse_txt_auto_detect_encoding_failure(self, mock_from_path):
        """Test _parse_txt raises ValueError when encoding detection fails."""
        mock_result = Mock()
        mock_result.best.return_value = None
        mock_from_path.return_value = mock_result

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("Test content")
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Failed to detect encoding"):
                MediaParser._parse_txt(temp_path, encoding=None)
        finally:
            os.unlink(temp_path)

    @patch("pdfplumber.open")
    def test_parse_pdf(self, mock_pdfplumber_open):
        """Test parsing a PDF file."""
        # Mock PDF pages
        mock_page1 = Mock()
        mock_page1.extract_text.return_value = "Page 1 text"

        mock_page2 = Mock()
        mock_page2.extract_text.return_value = "Page 2 text"

        # Mock pdfplumber PDF object with .pages attribute
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page1, mock_page2]

        # Mock the context manager behavior of pdfplumber.open
        mock_doc = MagicMock()
        mock_doc.__enter__.return_value = mock_pdf
        mock_pdfplumber_open.return_value = mock_doc

        # Create a real temp file so os.path.isfile passes
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            temp_path = f.name

        try:
            content = MediaParser._parse_pdf(temp_path)
            assert content == "Page 1 text\nPage 2 text"
            mock_pdfplumber_open.assert_called_once_with(temp_path)
        finally:
            os.unlink(temp_path)



    @patch("pdfplumber.open")
    def test_parse_pdf_empty_pages(self, mock_pdfplumber_open):
        """Test parsing PDF with empty pages."""
        # Mock page that returns empty text
        mock_page = Mock()
        mock_page.extract_text.return_value = ""

        # Mock pdfplumber PDF object
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]

        # Mock context manager result
        mock_doc = MagicMock()
        mock_doc.__enter__.return_value = mock_pdf
        mock_pdfplumber_open.return_value = mock_doc

        # Create a temporary .pdf file so os.path.isfile returns True
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            temp_path = f.name

        try:
            content = MediaParser._parse_pdf(temp_path)
            assert content == ""
            mock_pdfplumber_open.assert_called_once_with(temp_path)
        finally:
            os.unlink(temp_path)



    def test_parse_pdf_file_not_found(self):
        """Test parsing non-existent PDF raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="File not found"):
            MediaParser._parse_pdf("nonexistent.pdf")

    def test_get_text_txt_file(self):
        """Test get_text with .txt file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("Test content\x00with null")
            temp_path = f.name

        try:
            content = MediaParser.get_text(temp_path, encoding="utf-8")
            assert content == "Test contentwith null"
        finally:
            os.unlink(temp_path)

    @patch("pdfplumber.open")
    def test_get_text_pdf_file(self, mock_pdfplumber_open):
        """Test get_text with .pdf file."""
        # Mock a page that returns text via extract_text()
        mock_page = Mock()
        mock_page.extract_text.return_value = "PDF content"

        # Mock the pdfplumber PDF object with a .pages attribute
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]

        # Mock the context manager returned by pdfplumber.open
        mock_doc = MagicMock()
        mock_doc.__enter__.return_value = mock_pdf
        mock_pdfplumber_open.return_value = mock_doc

        # Create an actual temp file so os.path.isfile passes
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            temp_path = f.name

        try:
            content = MediaParser.get_text(temp_path)
            assert content == "PDF content"

            # Verify pdfplumber.open was called correctly
            mock_pdfplumber_open.assert_called_once_with(temp_path)
        finally:
            os.unlink(temp_path)



    @patch("railtracks.vector_stores.chunking.media_parser.MediaParser._parse_pdf")
    def test_get_text_passes_kwargs_only_to_supported_parser(self, mock_parse_pdf):
        """
        Ensure get_text passes **kwargs into the parser function without
        crashing even if kwargs contain irrelevant keys.
        """
        mock_parse_pdf.return_value = "Some PDF text"

        content = MediaParser.get_text("file.pdf", encoding="utf-8", foo="bar")

        assert content == "Some PDF text"
        mock_parse_pdf.assert_called_once()
        # kwargs should be forwarded; if you updated _parse_pdf(**kwargs),
        # this verifies the call succeeded.

    def test_get_text_unsupported_file_type(self):
        """Test get_text with unsupported file type."""
        with pytest.raises(ValueError, match="Unsupported file type: .docx"):
            MediaParser.get_text("file.docx")
