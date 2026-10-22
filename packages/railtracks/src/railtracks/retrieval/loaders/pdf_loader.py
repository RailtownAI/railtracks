from __future__ import annotations

import asyncio
import io
from collections.abc import AsyncGenerator, Mapping
from pathlib import Path
from typing import Any, Literal

from railtracks.retrieval.loaders._pdf_options import (
    BreakdownStrategy,
    validate_breakdown_strategy,
)
from railtracks.retrieval.loaders.base import BaseDocumentLoader
from railtracks.retrieval.models import Document, DocumentType

try:
    from pypdf import PdfReader
except ImportError as exc:
    raise ImportError(
        "pypdf is required for PyPDFLoader. "
        'Install it with: pip install "railtracks[pdf]"'
    ) from exc


async def stream_pdf(
    pdf: Path | bytes,
    *,
    source: str,
    breakdown_strategy: BreakdownStrategy = "page",
    metadata: Mapping[str, Any] | None = None,
) -> AsyncGenerator[Document, None]:
    """Stream documents extracted from one PDF, read from a path or from bytes.

    Yields one `Document` per page for the `page` strategy, one per non-empty
    paragraph for the `paragraph` strategy, or one `Document` for the entire
    PDF for the `document` strategy. See `PyPDFLoader` for the metadata each
    strategy adds.

    Args:
        pdf: Path to the PDF file, or the PDF's raw bytes.
        source: Value for each `Document.source`.
        breakdown_strategy: How to split the PDF into `Document` objects.
            Defaults to `page`.
        metadata: Extra metadata copied into every `Document`, before the
            PDF keys (`page`, `paragraph`, `total_pages`, `file_type`).

    Yields:
        Document: The next extracted document.
    """
    reader_input = io.BytesIO(pdf) if isinstance(pdf, bytes) else str(pdf)
    reader = await asyncio.to_thread(PdfReader, reader_input)
    total_pages = len(reader.pages)
    base_metadata = dict(metadata or {})

    def make_document(content: str, **position: int) -> Document:
        return Document(
            content=content,
            type=DocumentType.PDF,
            source=source,
            metadata={
                **base_metadata,
                **position,
                "total_pages": total_pages,
                "file_type": ".pdf",
            },
        )

    if breakdown_strategy == "document":
        page_texts = [
            await asyncio.to_thread(page.extract_text) or "" for page in reader.pages
        ]
        yield make_document("\n\n".join(page_texts))
        return

    extraction_mode: Literal["plain", "layout"] = (
        "layout" if breakdown_strategy == "paragraph" else "plain"
    )
    for page_number, page in enumerate(reader.pages, start=1):
        text = await asyncio.to_thread(
            page.extract_text, extraction_mode=extraction_mode
        )
        if not text or not text.strip():
            continue
        if breakdown_strategy == "page":
            yield make_document(text, page=page_number)
            continue
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        for paragraph_number, paragraph in enumerate(paragraphs, start=1):
            yield make_document(paragraph, page=page_number, paragraph=paragraph_number)


class PyPDFLoader(BaseDocumentLoader):
    """Loads PDF files as `Document` objects.

    If `file_path` points to a directory, all `.pdf` files are loaded
    recursively in sorted order. If it points to a file, that file is loaded.

    Breakdown strategies:

    - `page` *(default)*: one `Document` per page, yielded as each page is
      extracted. `metadata` includes `page` (1-based), `total_pages`, and
      `file_type`. Empty pages are skipped.
    - `paragraph`: one `Document` per non-empty paragraph on each page.
      Paragraphs are separated by ``\\n\\n``. `metadata` includes `page`
      (1-based), `paragraph` (1-based within the page), `total_pages`, and
      `file_type`.
    - `document`: entire PDF as one `Document`, with pages joined by ``\\n\\n``.
      `metadata` includes `total_pages` and `file_type`.

    Requires: ``pip install "railtracks[pdf]"``

    Args:
        file_path: Path to a `.pdf` file or a directory containing `.pdf` files.
        breakdown_strategy: How to split each PDF into `Document` objects.
            Defaults to `page`.

    Raises:
        FileNotFoundError: If `file_path` does not exist.
        ValueError: If `breakdown_strategy` is not `page`, `paragraph`, or
            `document`, or if `file_path` points to a file with an unsupported
            extension.
    """

    def __init__(
        self,
        file_path: str,
        breakdown_strategy: BreakdownStrategy = "page",
    ) -> None:
        self._path = Path(file_path)
        validate_breakdown_strategy(breakdown_strategy)
        self._breakdown_strategy: BreakdownStrategy = breakdown_strategy

    async def _stream_file(self, path: Path) -> AsyncGenerator[Document, None]:
        """Stream documents from a single PDF file.

        Args:
            path: Path to the PDF file to read.

        Yields:
            Document: The next extracted document.
        """
        async for doc in stream_pdf(
            path, source=str(path), breakdown_strategy=self._breakdown_strategy
        ):
            yield doc

    async def astream(self) -> AsyncGenerator[Document, None]:
        """Stream documents one at a time as each page or file is extracted.

        For the `page` and `paragraph` strategies, yields documents as soon
        as each page is extracted, allowing downstream stages to begin
        processing without waiting for the full PDF to load. For the
        `document` strategy, yields one `Document` per file after all pages
        are read.

        If initialised with a directory, streams documents from all `.pdf`
        files in sorted order.

        Yields:
            Document: The next extracted document.

        Raises:
            FileNotFoundError: If the path does not exist.
            ValueError: If the path points to a file with an unsupported
                extension.
        """
        if self._path.is_dir():
            for path in sorted(self._path.rglob("*.pdf")):
                if path.is_file():
                    async for doc in self._stream_file(path):
                        yield doc
            return

        if not self._path.is_file():
            raise FileNotFoundError(f"File not found: {self._path}")
        if self._path.suffix.lower() != ".pdf":
            raise ValueError(
                f"PyPDFLoader expects a .pdf file, got {self._path.suffix!r}"
            )

        async for doc in self._stream_file(self._path):
            yield doc
