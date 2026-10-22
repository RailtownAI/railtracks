from __future__ import annotations

import asyncio
import importlib.util
from abc import abstractmethod
from collections.abc import AsyncGenerator, Iterable
from pathlib import PurePosixPath

from railtracks.retrieval.loaders._pdf_options import (
    BreakdownStrategy,
    validate_breakdown_strategy,
)
from railtracks.retrieval.loaders.base import BaseDocumentLoader
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


def _suffix(key: str) -> str:
    return PurePosixPath(key).suffix.lower()


def infer_document_type(key: str) -> DocumentType:
    """Infer a :class:`DocumentType` from a storage key's file extension.

    Returns :attr:`DocumentType.TEXT` when the extension is unknown.
    """
    return _EXTENSION_TO_TYPE.get(_suffix(key), DocumentType.TEXT)


class ObjectStoreLoader(BaseDocumentLoader):
    """Shared loading loop for object stores such as S3, GCS and Azure Blob.

    Subclasses list and download objects and say how each one is named;
    this class turns each object into `Document` objects. PDFs (by extension)
    are parsed with the same logic as `PyPDFLoader`. Everything else is
    decoded as text in `encoding`. An object with a known text extension
    (`.txt`, `.md`, `.csv`, `.json`, `.jsonl`) that does not decode raises,
    since that points to a wrong `encoding`. Any other object that does not
    decode, such as an image, is skipped with a warning.

    Args:
        prefix: Only objects whose key starts with this string are listed.
            Ignored when `keys` is provided.
        keys: Explicit keys to load. When set, `prefix` is ignored.
        encoding: Text encoding used to decode non-PDF objects.
        pdf_breakdown_strategy: How to split each PDF into `Document` objects.

    Raises:
        ValueError: If `pdf_breakdown_strategy` is not a known strategy.
    """

    def __init__(
        self,
        *,
        prefix: str | None,
        keys: Iterable[str] | None,
        encoding: str,
        pdf_breakdown_strategy: BreakdownStrategy,
    ) -> None:
        validate_breakdown_strategy(
            pdf_breakdown_strategy, name="pdf_breakdown_strategy"
        )
        self._prefix = prefix
        self._keys = list(keys) if keys is not None else None
        self._encoding = encoding
        self._pdf_breakdown_strategy: BreakdownStrategy = pdf_breakdown_strategy

    @abstractmethod
    def _list_keys(self) -> list[str]:
        """Return every key under `self._prefix`. Runs in a worker thread."""

    @abstractmethod
    def _fetch_bytes(self, key: str) -> bytes:
        """Download one object's raw bytes. Runs in a worker thread."""

    @abstractmethod
    def _source(self, key: str) -> str:
        """Return the `Document.source` URI for `key`."""

    @abstractmethod
    def _metadata(self, key: str) -> dict[str, str]:
        """Return the provider metadata copied into every `Document` from `key`."""

    async def astream(self) -> AsyncGenerator[Document, None]:
        """Stream documents one at a time as each object is downloaded.

        Yields:
            Document: The next loaded document.

        Raises:
            ImportError: If any key is a PDF and `pypdf` is not installed.
                Raised before the first object is downloaded.
            ValueError: If an object with a known text extension is not valid
                text in `encoding`.
        """
        if self._keys is not None:
            keys = self._keys
        else:
            keys = await asyncio.to_thread(self._list_keys)

        first_pdf = next(
            (key for key in keys if infer_document_type(key) is DocumentType.PDF),
            None,
        )
        if first_pdf is not None and importlib.util.find_spec("pypdf") is None:
            raise ImportError(
                f"pypdf is required to load the PDF {self._source(first_pdf)!r}. "
                'Install it with: pip install "railtracks[pdf]"'
            )

        for key in keys:
            data = await asyncio.to_thread(self._fetch_bytes, key)
            async for doc in self._stream_object(key, data):
                yield doc

    async def _stream_object(
        self, key: str, data: bytes
    ) -> AsyncGenerator[Document, None]:
        """Turn one downloaded object into `Document` objects."""
        source = self._source(key)
        document_type = infer_document_type(key)
        if document_type is DocumentType.PDF:
            # Deferred so text-only loads work without the optional `pdf` extra.
            from railtracks.retrieval.loaders.pdf_loader import stream_pdf

            async for doc in stream_pdf(
                data,
                source=source,
                breakdown_strategy=self._pdf_breakdown_strategy,
                metadata=self._metadata(key),
            ):
                yield doc
            return

        try:
            content = await asyncio.to_thread(data.decode, self._encoding)
        except UnicodeDecodeError as exc:
            if _suffix(key) in _EXTENSION_TO_TYPE:
                raise ValueError(
                    f"{source!r} is not valid {self._encoding} text: {exc!r}. "
                    "Pass `encoding=` if it uses another encoding."
                ) from exc
            logger.warning(
                "Skipping %s: it is not valid %s text, and only PDFs are loaded "
                "as binary files. If it is text in another encoding, pass `encoding=`.",
                source,
                self._encoding,
            )
            return
        yield Document(
            content=content,
            type=document_type,
            source=source,
            metadata=self._metadata(key),
        )
