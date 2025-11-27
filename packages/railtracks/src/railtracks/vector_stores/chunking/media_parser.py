import os
from typing import Optional

import pymupdf
from charset_normalizer import from_path


class MediaParser:
    """General-purpose media parser capable of extracting text from various file types.

    Currently supports:
        - .txt
        - .pdf
    """

    _PARSERS = {
        ".txt": "_parse_txt",
        ".pdf": "_parse_pdf",
    }

    @classmethod
    def get_text(cls, path: str, **kwargs) -> str:
        """Return cleaned text extracted from a supported file.

        Args:
            path: Path to the file
            **kwargs: Parser-specific arguments (e.g., encoding for .txt files)
        """
        ext = cls._get_extension(path)
        handler_name = cls._PARSERS.get(ext)

        if not handler_name:
            raise ValueError(f"Unsupported file type: {ext}")

        parser_function = getattr(cls, handler_name)
        raw_text = parser_function(path, **kwargs)  # Pass kwargs through
        return cls._clean_text(raw_text)

    @classmethod
    def _parse_txt(cls, filepath: str, encoding: Optional[str] = None, **kwargs) -> str:
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

    @classmethod
    def _parse_pdf(cls, filepath: str) -> str:
        """Extract text from a PDF using PyMuPDF (pymupdf)."""
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        with pymupdf.open(filepath) as doc:
            extracted = []
            for page in doc:
                text = page.get_text()
                if text:
                    extracted.append(text)
            return "\n".join(extracted)

    @classmethod
    def _clean_text(cls, text: str) -> str:
        """Remove null bytes / non-printable characters while preserving whitespace."""
        if not text:
            return ""
        return "".join(char for char in text if char.isprintable() or char in "\t\n\r")

    @staticmethod
    def _get_extension(path: str) -> str:
        """Return file extension in lowercase."""
        _, ext = os.path.splitext(path)
        return ext.lower()
