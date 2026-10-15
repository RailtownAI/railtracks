from __future__ import annotations

from collections.abc import AsyncGenerator, Mapping
from pathlib import PurePosixPath
from typing import Any

from railtracks.retrieval.loaders._pdf_options import BreakdownStrategy
from railtracks.retrieval.models import Document, DocumentType
from railtracks.utils.logging.create import get_rt_logger

logger = get_rt_logger(__name__)

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


async def stream_object_documents(
    data: bytes,
    *,
    key: str,
    source: str,
    metadata: Mapping[str, Any],
    encoding: str,
    pdf_breakdown_strategy: BreakdownStrategy,
) -> AsyncGenerator[Document, None]:
    """Turn one downloaded storage object into `Document` objects.

    PDFs (by extension) are parsed with the same logic as `PyPDFLoader`.
    Everything else is decoded as text. An object that is not valid text in
    `encoding` is skipped with a warning, so one binary file does not stop
    the whole load.

    Args:
        data: The object's raw bytes.
        key: The object's key or name, used to infer its type.
        source: Value for each `Document.source`.
        metadata: Provider metadata copied into every `Document`.
        encoding: Text encoding used to decode non-PDF objects.
        pdf_breakdown_strategy: How to split a PDF into `Document` objects.

    Yields:
        Document: The next document from this object.

    Raises:
        ImportError: If the object is a PDF and `pypdf` is not installed.
    """
    document_type = infer_document_type(key)
    if document_type is DocumentType.PDF:
        try:
            from railtracks.retrieval.loaders.pdf_loader import stream_pdf
        except ImportError as exc:
            raise ImportError(
                f"pypdf is required to load the PDF {source!r}. "
                'Install it with: pip install "railtracks[pdf]"'
            ) from exc
        async for doc in stream_pdf(
            data,
            source=source,
            breakdown_strategy=pdf_breakdown_strategy,
            metadata=metadata,
        ):
            yield doc
        return

    try:
        content = data.decode(encoding)
    except UnicodeDecodeError:
        logger.warning(
            "Skipping %s: it is not valid %s text, and only PDFs are loaded "
            "as binary files. If it is text in another encoding, pass `encoding=`.",
            source,
            encoding,
        )
        return
    yield Document(
        content=content, type=document_type, source=source, metadata=dict(metadata)
    )
