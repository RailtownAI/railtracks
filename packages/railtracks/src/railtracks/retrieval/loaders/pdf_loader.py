from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Literal

from railtracks.retrieval.loaders.base import BaseDocumentLoader
from railtracks.retrieval.models import Document, DocumentType

try:
    from pypdf import PdfReader
except ImportError as exc:
    raise ImportError(
        "pypdf is required for PyPDFLoader. "
        'Install it with: pip install "railtracks[pdf]"'
    ) from exc


BreakdownStrategy = Literal["page", "document"]


class PyPDFLoader(BaseDocumentLoader):
    """Loads PDF files as `Document` objects.

    If `file_path` points to a directory, all `.pdf` files are loaded
    recursively in sorted order. If it points to a file, that file is loaded.

    Breakdown strategies:

    - `page` *(default)*: one `Document` per page, yielded as each page is
      extracted. `metadata` includes `page` (1-based), `total_pages`, and
      `file_type`. Empty pages are skipped.
    - `document`: entire PDF as one `Document`, with pages joined by ``\\n\\n``.
      `metadata` includes `total_pages` and `file_type`.

    Requires: ``pip install "railtracks[pdf]"``

    Args:
        file_path: Path to a `.pdf` file or a directory containing `.pdf` files.
        breakdown_strategy: How to split each PDF into `Document` objects.
            Defaults to `page`.

    Raises:
        FileNotFoundError: If `file_path` does not exist.
        ValueError: If `breakdown_strategy` is not `page` or `document`, or if
            `file_path` points to a file with an unsupported extension.
    """

    def __init__(
        self,
        file_path: str,
        breakdown_strategy: BreakdownStrategy = "page",
    ) -> None:
        self._path = Path(file_path)
        if breakdown_strategy not in ("page", "document"):
            raise ValueError(
                f"breakdown_strategy must be 'page' or 'document', got {breakdown_strategy!r}"
            )
        self._breakdown_strategy = breakdown_strategy

    async def _stream_file(self, path: Path) -> AsyncGenerator[Document, None]:
        """Stream documents from a single PDF file.

        Yields one `Document` per page for the `page` strategy, or one
        `Document` for the entire file for the `document` strategy.

        Args:
            path: Path to the PDF file to read.

        Yields:
            Document: The next extracted document.
        """
        reader = await asyncio.to_thread(PdfReader, str(path))
        total_pages = len(reader.pages)
        source = str(path)

        if self._breakdown_strategy == "document":
            content = "\n\n".join(
                page.extract_text() or "" for page in reader.pages
            )
            yield Document(
                content=content,
                type=DocumentType.PDF,
                source=source,
                metadata={"total_pages": total_pages, "file_type": ".pdf"},
            )
            return

        for page_number, page in enumerate(reader.pages, start=1):
            text = await asyncio.to_thread(page.extract_text)
            if not text or not text.strip():
                continue
            yield Document(
                content=text,
                type=DocumentType.PDF,
                source=source,
                metadata={
                    "page": page_number,
                    "total_pages": total_pages,
                    "file_type": ".pdf",
                },
            )

    async def astream(self) -> AsyncGenerator[Document, None]:
        """Stream documents one at a time as each page or file is extracted.

        For the `page` strategy, yields one `Document` per page as soon as
        it is extracted, allowing downstream stages to begin processing
        without waiting for the full PDF to load. For the `document`
        strategy, yields one `Document` per file after all pages are read.

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