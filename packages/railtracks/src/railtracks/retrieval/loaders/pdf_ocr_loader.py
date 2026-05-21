from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from railtracks.retrieval.loaders.base_ocr import BaseOCRLoader
from railtracks.retrieval.models import Document, DocumentType

try:
    import pypdfium2 as pdfium
    import pytesseract
    from pypdf import PdfReader
except ImportError as exc:
    raise ImportError(
        "pypdfium2, pytesseract, pillow, and pypdf are required for "
        'PyPDFOCRLoader. Install them with: pip install "railtracks[ocr]". '
        "You must also install the Tesseract binary on your system and "
        "ensure it is on PATH. Install instructions: "
        "https://tesseract-ocr.github.io/tessdoc/Installation.html"
    ) from exc

if TYPE_CHECKING:
    from PIL.Image import Image


BreakdownStrategy = Literal["page", "document"]

# pypdfium2's `render()` takes a `scale` multiplier where 1.0 == 72 DPI
# (PDF's native unit). scale = target_dpi / 72.
_PDFIUM_BASE_DPI = 72

# 300 DPI is the standard sweet spot for Tesseract: below ~200 accuracy
# degrades sharply on small text; above ~400 produces negligible accuracy
# gains for materially more time and memory.
_DEFAULT_OCR_DPI = 300


class PyPDFOCRLoader(BaseOCRLoader):
    """Loads PDF files as `Document` objects, falling back to OCR per page.

    For each page, the loader first attempts to extract embedded text via
    `pypdf`. Pages where text extraction returns empty (e.g. scanned pages
    with no text layer) are rasterized with `pypdfium2` and recognized with
    Tesseract via `pytesseract`. This means a single PDF can mix
    text-extracted pages and OCR-extracted pages transparently.

    Pass `force_ocr=True` to OCR every page regardless of whether it has a
    text layer.

    If `file_path` points to a directory, all `.pdf` files are loaded
    recursively in sorted order. If it points to a file, that file is loaded.

    Breakdown strategies:

    - `page` *(default)*: one `Document` per page, yielded as each page is
      extracted. `metadata` includes `page` (1-based), `total_pages`,
      `file_type`, and `ocr` (bool indicating whether OCR was used for that
      page). Empty pages are skipped.
    - `document`: entire PDF as one `Document`, with pages joined by `\\n\\n`.
      `metadata` includes `total_pages`, `file_type`, and `ocr_pages`
      (sorted list of 1-based page numbers that required OCR).

    Requires:
        - ``pip install "railtracks[ocr]"`` (Python libraries)
        - Tesseract binary installed and on PATH
          (https://github.com/UB-Mannheim/tesseract/wiki on Windows)

    Args:
        file_path: Path to a `.pdf` file or a directory containing `.pdf` files.
        breakdown_strategy: How to split each PDF into `Document` objects.
            Defaults to `page`.
        force_ocr: If `True`, OCR every page without first checking for an
            embedded text layer. Defaults to `False` (auto-fallback).
        dpi: Rendering resolution when rasterizing pages for OCR. Higher
            values improve accuracy at the cost of speed/memory. Defaults
            to 300.
        language: Tesseract language code (e.g. `"eng"`, `"eng+deu"`).
            Defaults to `"eng"`.

    Raises:
        FileNotFoundError: If `file_path` does not exist.
        ValueError: If `breakdown_strategy` is not `page` or `document`, if
            `dpi` is non-positive, or if `file_path` points to a file with
            an unsupported extension.
    """

    def __init__(
        self,
        file_path: str,
        breakdown_strategy: BreakdownStrategy = "page",
        force_ocr: bool = False,
        dpi: int = _DEFAULT_OCR_DPI,
        language: str = "eng",
    ) -> None:
        self._path = Path(file_path)
        if breakdown_strategy not in ("page", "document"):
            raise ValueError(
                f"breakdown_strategy must be 'page' or 'document', got {breakdown_strategy!r}"
            )
        if dpi <= 0:
            raise ValueError(f"dpi must be a positive integer, got {dpi!r}")
        self._breakdown_strategy = breakdown_strategy
        self._force_ocr = force_ocr
        self._dpi = dpi
        self._language = language

    async def _ocr_image(self, image: Image) -> str:
        """OCR a single image using pytesseract.

        Runs the blocking Tesseract subprocess in a worker thread so the
        async pipeline keeps flowing while OCR is in progress.
        """
        text = await asyncio.to_thread(
            pytesseract.image_to_string, image, lang=self._language
        )
        return text or ""

    def _render_page_image(self, pdf_page) -> Image:
        """Rasterize a single pypdfium2 page to a PIL Image at `self._dpi`."""
        scale = self._dpi / _PDFIUM_BASE_DPI
        bitmap = pdf_page.render(scale=scale)
        return bitmap.to_pil()

    async def _extract_embedded_text(self, reader: PdfReader, page_index: int) -> str:
        """Return embedded text for a page, or `""` if none/whitespace-only."""
        page = reader.pages[page_index]
        text = await asyncio.to_thread(page.extract_text)
        if not text or not text.strip():
            return ""
        return text

    async def _resolve_page_text(
        self,
        reader: PdfReader,
        pdf: pdfium.PdfDocument,
        page_index: int,
    ) -> tuple[str, bool]:
        """Return `(text, used_ocr)` for a single page.

        Tries embedded-text extraction first unless `force_ocr` is set; falls
        back to OCR when the text layer is empty or `force_ocr` is `True`.
        """
        if not self._force_ocr:
            text = await self._extract_embedded_text(reader, page_index)
            if text:
                return text, False

        image = await asyncio.to_thread(self._render_page_image, pdf[page_index])
        text = await self._ocr_image(image)
        return text, True

    async def _stream_file(self, path: Path) -> AsyncGenerator[Document, None]:
        """Stream `Document`s from a single PDF file."""
        reader = await asyncio.to_thread(PdfReader, str(path))
        pdf = await asyncio.to_thread(pdfium.PdfDocument, str(path))
        total_pages = len(reader.pages)
        source = str(path)

        try:
            if self._breakdown_strategy == "document":
                page_texts: list[str] = []
                ocr_pages: list[int] = []
                for page_index in range(total_pages):
                    text, used_ocr = await self._resolve_page_text(
                        reader, pdf, page_index
                    )
                    # Skip empty/whitespace-only pages so the joined output
                    # doesn't accumulate blank `\n\n` gaps where blank pages
                    # would have been. Matches the page-strategy behaviour.
                    if not text or not text.strip():
                        continue
                    page_texts.append(text)
                    if used_ocr:
                        ocr_pages.append(page_index + 1)
                yield Document(
                    content="\n\n".join(page_texts),
                    type=DocumentType.PDF,
                    source=source,
                    metadata={
                        "total_pages": total_pages,
                        "file_type": ".pdf",
                        "ocr_pages": ocr_pages,
                    },
                )
                return

            for page_index in range(total_pages):
                text, used_ocr = await self._resolve_page_text(reader, pdf, page_index)
                if not text or not text.strip():
                    continue
                yield Document(
                    content=text,
                    type=DocumentType.PDF,
                    source=source,
                    metadata={
                        "page": page_index + 1,
                        "total_pages": total_pages,
                        "file_type": ".pdf",
                        "ocr": used_ocr,
                    },
                )
        finally:
            # Both backends hold the file open until explicitly closed.
            # Skipping either would leak a file handle per PDF, which
            # becomes a real problem when streaming a directory.
            await asyncio.to_thread(pdf.close)
            await asyncio.to_thread(reader.close)

    async def astream(self) -> AsyncGenerator[Document, None]:
        """Stream documents one at a time as each page or file is processed.

        For the `page` strategy, yields one `Document` per non-empty page as
        soon as it is extracted, allowing downstream stages to begin
        processing without waiting for the full PDF. For the `document`
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
                f"PyPDFOCRLoader expects a .pdf file, got {self._path.suffix!r}"
            )

        async for doc in self._stream_file(self._path):
            yield doc
