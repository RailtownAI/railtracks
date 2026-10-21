from __future__ import annotations

from io import BytesIO
from pathlib import PurePosixPath

from railtracks.retrieval.models import DocumentType

_EXTENSION_TO_TYPE: dict[str, DocumentType] = {
    ".md": DocumentType.MARKDOWN,
    ".markdown": DocumentType.MARKDOWN,
    ".csv": DocumentType.CSV,
    ".json": DocumentType.JSON,
    ".jsonl": DocumentType.JSONL,
    ".pdf": DocumentType.PDF,
    ".txt": DocumentType.TEXT,
}


def infer_document_type(key: str) -> DocumentType:
    """Infer a :class:`DocumentType` from a storage key's file extension.

    Returns :attr:`DocumentType.TEXT` when the extension is unknown.
    """
    suffix = PurePosixPath(key).suffix.lower()
    return _EXTENSION_TO_TYPE.get(suffix, DocumentType.TEXT)


def decode_object(key: str, data: bytes, encoding: str) -> str:
    """Turn a downloaded object's bytes into document text.

    PDF objects are parsed with ``pypdf`` and their pages joined by blank
    lines; every other object is decoded as text with ``encoding``.

    Args:
        key: The object's storage key, used to detect PDFs by extension.
        data: The object's raw bytes.
        encoding: Text encoding for non-PDF objects.

    Raises:
        ImportError: If the object is a PDF and ``pypdf`` is not installed.
        UnicodeDecodeError: If a non-PDF object is not valid ``encoding`` text.
    """
    if infer_document_type(key) is DocumentType.PDF:
        return _extract_pdf_text(data)
    return data.decode(encoding)


def _extract_pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ImportError(
            "pypdf is required to load PDF objects from cloud storage. "
            'Install it with: pip install "railtracks[pdf]"'
        ) from exc
    reader = PdfReader(BytesIO(data))
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)
