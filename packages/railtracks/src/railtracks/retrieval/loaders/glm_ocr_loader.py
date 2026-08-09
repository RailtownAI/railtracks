from __future__ import annotations

import asyncio
import base64
import io
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from railtracks.retrieval.loaders.base_ocr import BaseOCRLoader
from railtracks.retrieval.models import Document, DocumentType, OCRResult

try:
    import glmocr
    from PIL import Image as PILImage
except ImportError as exc:
    raise ImportError(
        "glmocr and pillow are required for GLMOCRLoader. "
        'Install them with: pip install "railtracks[glm]".'
    ) from exc

if TYPE_CHECKING:
    from PIL.Image import Image


BreakdownStrategy = Literal["page", "document"]

_SUPPORTED_IMAGE_SUFFIXES = frozenset(
    {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
)

_SUPPORTED_SUFFIXES = _SUPPORTED_IMAGE_SUFFIXES | frozenset({".pdf"})


def _parse_glmocr_response(raw: dict) -> OCRResult:
    return OCRResult(
        markdown=raw.get("markdown", ""),
        bboxes=raw.get("bboxes", []),
        tables=raw.get("tables", []),
    )


class GLMOCRLoader(BaseOCRLoader):
    """Loads image and PDF files as ``Document`` objects using GLM-OCR.

    Selects cloud or local execution based on ``endpoint``:

    - ``endpoint=None`` *(default)*: delegates to the Zhipu cloud API via the
      ``glmocr`` SDK. Requires an API key configured in the environment per the
      glmocr SDK docs. Blocking SDK calls are offloaded to a thread pool.
    - ``endpoint="https://…"`` (non-empty URL): POSTs files to a self-hosted
      vLLM/Ollama server using ``httpx.AsyncClient``.

    Handles both file types:

    - **Image files** (``.bmp``, ``.jpeg``, ``.jpg``, ``.png``, ``.tif``,
      ``.tiff``, ``.webp``): opened with PIL and sent as base64-encoded PNG.
      The delegation between ``_ocr_image`` and ``_ocr_image_structured`` is
      *inverted* from the base-class default: ``_ocr_image_structured`` is the
      real implementation and ``_ocr_image`` derives flat text from it via
      ``to_text()``.
    - **PDF files** (``.pdf``): read as raw bytes and sent to GLM-OCR's native
      PDF endpoint. This avoids rasterization and preserves layout-aware output
      (headings, tables, column order) in a single round-trip.

    Breakdown strategies:

    - ``page`` *(default)*: one ``Document`` per file. ``metadata`` includes
      ``file_type``, ``bboxes``, and ``tables``.
    - ``document``: all files in a directory are concatenated into one
      ``Document`` with pages joined by ``\\n\\n``. ``metadata`` aggregates
      ``bboxes`` and ``tables`` from every file.

    Requires:
        ``pip install "railtracks[glm]"``

    Args:
        file_path: Path to an image or PDF file, or a directory of such files.
            Supported extensions: ``.bmp``, ``.jpeg``, ``.jpg``, ``.pdf``,
            ``.png``, ``.tif``, ``.tiff``, ``.webp``.
        endpoint: Base URL of a self-hosted vLLM/Ollama OCR server. Pass
            ``None`` (default) to use the Zhipu cloud API via the ``glmocr``
            SDK; pass a non-empty URL string to POST to a local endpoint instead.
        breakdown_strategy: How to aggregate results across files in a
            directory. Defaults to ``"page"``.

    Raises:
        ValueError: If ``endpoint`` is an empty string.
        ValueError: If ``breakdown_strategy`` is not ``"page"`` or
            ``"document"``.
        FileNotFoundError: If ``file_path`` does not exist (raised from
            ``astream()``).
        ValueError: If ``file_path`` points to a file with an unsupported
            extension (raised from ``astream()``).
    """

    def __init__(
        self,
        file_path: str,
        endpoint: str | None = None,
        breakdown_strategy: BreakdownStrategy = "page",
    ) -> None:
        self._path = Path(file_path)
        if endpoint is not None and not endpoint:
            raise ValueError("endpoint must be a non-empty string or None")
        if breakdown_strategy not in ("page", "document"):
            raise ValueError(
                f"breakdown_strategy must be 'page' or 'document', "
                f"got {breakdown_strategy!r}"
            )
        self._endpoint = endpoint
        self._breakdown_strategy = breakdown_strategy
        self._is_pdf = self._path.suffix.lower() == ".pdf"
        if self._endpoint is None:
            self._call = self._call_cloud
            self._call_pdf = self._call_cloud_pdf
        else:
            self._call = self._call_local
            self._call_pdf = self._call_local_pdf

    async def _ocr_image(self, image: Image) -> str:
        """Return flat text by delegating to the structured path.

        Inverts the base-class default: ``_ocr_image_structured`` is the real
        implementation here; this method exists only to satisfy the abstract
        contract and preserve backward compatibility with callers that expect
        a plain ``str``.
        """
        result = await self._ocr_image_structured(image)
        return result.to_text()

    async def _ocr_image_structured(self, image: Image) -> OCRResult:
        """OCR a single image using GLM-OCR, returning structured output."""
        return await self._call(image)

    async def _ocr_pdf_structured(self, pdf_bytes: bytes) -> OCRResult:
        """Send raw PDF bytes to GLM-OCR and return structured output."""
        return await self._call_pdf(pdf_bytes)

    async def _call_cloud(self, image: Image) -> OCRResult:
        """Send a PIL image to the Zhipu cloud API via the glmocr SDK.

        Encodes the image as PNG bytes in the calling thread, then offloads
        the blocking network call to a worker thread.
        """
        buf = io.BytesIO()
        await asyncio.to_thread(image.save, buf, format="PNG")
        image_bytes = buf.getvalue()
        raw: dict = await asyncio.to_thread(glmocr.ocr, image_bytes)
        return _parse_glmocr_response(raw)

    async def _call_local(self, image: Image) -> OCRResult:
        """POST a PIL image to a local vLLM/Ollama endpoint.

        Sends the image as a base64-encoded PNG in a JSON body and reads the
        response with ``httpx.AsyncClient`` so the event loop is not blocked.
        """
        import httpx

        buf = io.BytesIO()
        await asyncio.to_thread(image.save, buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self._endpoint,  # type: ignore[arg-type]  # non-None guaranteed by __init__
                json={"image": b64, "format": "markdown"},
                timeout=60.0,
            )
            response.raise_for_status()
            raw: dict = response.json()

        return _parse_glmocr_response(raw)

    async def _call_cloud_pdf(self, pdf_bytes: bytes) -> OCRResult:
        """Send PDF bytes to the Zhipu cloud API via the glmocr SDK."""
        raw: dict = await asyncio.to_thread(glmocr.ocr, pdf_bytes, format="pdf")
        return _parse_glmocr_response(raw)

    async def _call_local_pdf(self, pdf_bytes: bytes) -> OCRResult:
        """POST PDF bytes (base64-encoded) to the local endpoint."""
        import httpx

        b64 = base64.b64encode(pdf_bytes).decode()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self._endpoint,  # type: ignore[arg-type]  # non-None guaranteed by __init__
                json={"pdf": b64, "format": "pdf"},
                timeout=120.0,
            )
            response.raise_for_status()
            raw: dict = response.json()
        return _parse_glmocr_response(raw)

    async def _stream_image(self, path: Path) -> AsyncGenerator[Document, None]:
        """Yield a single Document from one image file."""
        image = await asyncio.to_thread(PILImage.open, path)
        result = await self._ocr_image_structured(image)
        if not result.markdown or not result.markdown.strip():
            return
        yield Document(
            content=result.markdown,
            type=DocumentType.TEXT,
            source=str(path),
            metadata={
                "file_type": path.suffix.lower(),
                "bboxes": result.bboxes,
                "tables": result.tables,
            },
        )

    async def _stream_pdf(self, path: Path) -> AsyncGenerator[Document, None]:
        """Yield a Document from one PDF file by passing its bytes to GLM-OCR."""
        pdf_bytes = await asyncio.to_thread(path.read_bytes)
        result = await self._ocr_pdf_structured(pdf_bytes)
        if not result.markdown or not result.markdown.strip():
            return
        yield Document(
            content=result.markdown,
            type=DocumentType.PDF,
            source=str(path),
            metadata={
                "file_type": ".pdf",
                "bboxes": result.bboxes,
                "tables": result.tables,
            },
        )

    async def _stream_file(self, path: Path) -> AsyncGenerator[Document, None]:
        """Dispatch to _stream_pdf or _stream_image based on file extension."""
        if path.suffix.lower() == ".pdf":
            async for doc in self._stream_pdf(path):
                yield doc
        else:
            async for doc in self._stream_image(path):
                yield doc

    async def _stream_dir(self) -> AsyncGenerator[Document, None]:
        """Stream Documents from a directory of image and PDF files.

        Handles both breakdown strategies so ``astream()`` stays simple.
        """
        paths = sorted(
            p
            for p in self._path.rglob("*")
            if p.is_file() and p.suffix.lower() in _SUPPORTED_SUFFIXES
        )
        if self._breakdown_strategy == "document":
            page_texts: list[str] = []
            all_bboxes: list[dict] = []
            all_tables: list[dict] = []
            for path in paths:
                async for doc in self._stream_file(path):
                    page_texts.append(doc.content)
                    all_bboxes.extend(doc.metadata.get("bboxes", []))
                    all_tables.extend(doc.metadata.get("tables", []))
            if page_texts:
                yield Document(
                    content="\n\n".join(page_texts),
                    type=DocumentType.TEXT,
                    source=str(self._path),
                    metadata={"bboxes": all_bboxes, "tables": all_tables},
                )
            return
        for path in paths:
            async for doc in self._stream_file(path):
                yield doc

    async def astream(self) -> AsyncGenerator[Document, None]:
        """Stream Documents from image and PDF files using GLM-OCR.

        For the ``page`` strategy, yields one ``Document`` per non-empty file
        as soon as it is processed. For the ``document`` strategy, yields one
        ``Document`` per directory after all files are collected.

        If initialised with a directory, iterates all supported image and PDF
        files in sorted order (recursively).

        Yields:
            Document: The next extracted document.

        Raises:
            FileNotFoundError: If the path does not exist.
            ValueError: If the path points to a file with an unsupported
                extension.
        """
        if self._path.is_dir():
            async for doc in self._stream_dir():
                yield doc
            return
        if not self._path.is_file():
            raise FileNotFoundError(f"File not found: {self._path}")
        if self._is_pdf:
            async for doc in self._stream_pdf(self._path):
                yield doc
            return
        if self._path.suffix.lower() not in _SUPPORTED_IMAGE_SUFFIXES:
            raise ValueError(
                f"GLMOCRLoader expects an image or PDF file "
                f"({', '.join(sorted(_SUPPORTED_SUFFIXES))}), "
                f"got {self._path.suffix!r}"
            )
        async for doc in self._stream_image(self._path):
            yield doc
