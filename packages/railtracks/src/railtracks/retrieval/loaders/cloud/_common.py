from __future__ import annotations

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
