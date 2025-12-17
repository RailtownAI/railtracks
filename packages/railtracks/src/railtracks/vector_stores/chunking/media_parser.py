import os
from typing import Optional

from charset_normalizer import from_path

_pdfplumber = None


class MediaParser:
    """General-purpose media parser capable of extracting text from various file types.

    Currently supports:
        - .txt
        - .pdf
    """

    @classmethod
    def get_text(cls, path: str, **kwargs) -> str:
        """Return cleaned text extracted from a supported file.

        Args:
            path: Path to the file
            **kwargs: Parser-specific arguments (e.g., encoding for .txt files)
        """
        ext = cls._get_extension(path)
        if ext == ".txt":
            handler_name = "_parse_txt"

        elif ext == ".pdf":
            handler_name = "_parse_pdf"

        else:
            raise ValueError(f"Unsupported file type: {ext}")

        parser_function = getattr(cls, handler_name)
        raw_text = parser_function(path, **kwargs)  # Pass kwargs through
        return cls._clean_text(raw_text)

    @staticmethod
    def _parse_txt(filepath: str, encoding: Optional[str] = None, **kwargs) -> str:
        """Extract text from a plain .txt file."""
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        if encoding is not None:
            with open(filepath, "r", encoding=encoding) as f:
                return f.read()

        # Auto-detect encoding
        detected = from_path(filepath).best()
        if detected is None:
            raise ValueError(f"Failed to detect encoding for: {filepath}")

        with open(filepath, "r", encoding=detected.encoding) as f:
            return f.read()

    @staticmethod
    def _parse_pdf(filepath: str, **kwargs) -> str:
        """Extract text from a PDF using pdfplumber."""
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        global _pdfplumber

        if _pdfplumber is None:
            try:
                import pdfplumber

                _pdfplumber = pdfplumber
            except ImportError:
                raise RuntimeError(
                    "pdfplumber is required for PDF parsing but isn't installed. "
                    "Install it via `pip install pdfplumber`."
                )

        with _pdfplumber.open(filepath) as doc:
            extracted = []
            for page in doc.pages:
                text = page.extract_text()
                if text:
                    extracted.append(text)
            return "\n".join(extracted)

    @staticmethod
    def _clean_text(text: str) -> str:
        """Remove null bytes / non-printable characters while preserving whitespace."""
        if not text:
            return ""
        return "".join(char for char in text if char.isprintable() or char in "\t\n\r")

    @staticmethod
    def _get_extension(path: str) -> str:
        """Return file extension in lowercase."""
        _, ext = os.path.splitext(path)
        return ext.lower()
