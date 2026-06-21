from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from railtracks.retrieval.loaders.base_ocr import BaseOCRLoader
from railtracks.retrieval.models import Document, DocumentType, OCRResult

try:
    import glmocr
except ImportError as exc:
    raise ImportError(
        "glmocr is required for GLMOCRLoader and GLMOCRPDFLoader. "
        'Install it with: pip install "railtracks[glm]".'
    ) from exc

if TYPE_CHECKING:
    from PIL.Image import Image


BreakdownStrategy = Literal["page", "document"]

_SUPPORTED_IMAGE_SUFFIXES = frozenset(
    {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
)


def _parse_glmocr_response(raw: dict) -> OCRResult:
    # TODO: Confirm actual GLM-OCR JSON response schema once SDK docs are
    # published. Current stub assumes:
    #   raw["markdown"]         str        — full page text in markdown format
    #   raw.get("bboxes", [])   list[dict] — bounding-box annotations (optional)
    #   raw.get("tables", [])   list[dict] — extracted table data (optional)
    return OCRResult(
        markdown=raw.get("markdown", ""),
        bboxes=raw.get("bboxes", []),
        tables=raw.get("tables", []),
    )


class GLMOCRLoader(BaseOCRLoader):
    """Loads image files as ``Document`` objects using GLM-OCR for structured extraction.

    Supports two deployment modes:

    - ``cloud`` *(default)*: delegates to the Zhipu cloud API via the ``glmocr``
      SDK. Requires an API key configured in the environment per the glmocr SDK
      docs. The blocking SDK call is offloaded to a thread pool.
    - ``local``: POSTs images to a self-hosted vLLM/Ollama endpoint at
      ``endpoint``. The endpoint must accept
      ``{"image": <base64-PNG>, "format": "markdown"}`` and return the same JSON
      schema as the cloud API. Uses ``httpx.AsyncClient`` for the async HTTP call.

    Unlike :class:`PyPDFOCRLoader`, which rasterizes PDF pages and runs Tesseract
    on each image, this loader receives structured output (markdown, bounding
    boxes, tables) from GLM-OCR in a single round-trip. The delegation between
    ``_ocr_image`` and ``_ocr_image_structured`` is therefore *inverted* from the
    base-class default: ``_ocr_image_structured`` is the real implementation and
    ``_ocr_image`` derives flat text from it via ``to_text()``.

    Breakdown strategies:

    - ``page`` *(default)*: one ``Document`` per image file. ``metadata`` includes
      ``file_type``, ``bboxes``, and ``tables``.
    - ``document``: all images in a directory are concatenated into one
      ``Document`` with pages joined by ``\\n\\n``. ``metadata`` aggregates
      ``bboxes`` and ``tables`` from every file.

    Requires:
        ``pip install "railtracks[glm]"``

    Args:
        file_path: Path to an image file or a directory of image files.
            Supported extensions: ``.bmp``, ``.jpeg``, ``.jpg``, ``.png``,
            ``.tif``, ``.tiff``, ``.webp``.
        mode: Deployment mode — ``"cloud"`` or ``"local"``. Defaults to
            ``"cloud"``.
        endpoint: Base URL of the local OCR endpoint. Required when
            ``mode="local"``; ignored otherwise.
        breakdown_strategy: How to aggregate results across files in a
            directory. Defaults to ``"page"``.

    Raises:
        ValueError: If ``mode`` is not ``"cloud"`` or ``"local"``.
        ValueError: If ``mode="local"`` and ``endpoint`` is ``None``.
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
        mode: Literal["cloud", "local"] = "cloud",
        endpoint: str | None = None,
        breakdown_strategy: BreakdownStrategy = "page",
    ) -> None:
        self._path = Path(file_path)
        if mode not in ("cloud", "local"):
            raise ValueError(f"mode must be 'cloud' or 'local', got {mode!r}")
        if mode == "local" and endpoint is None:
            raise ValueError("endpoint is required when mode='local'")
        if breakdown_strategy not in ("page", "document"):
            raise ValueError(
                f"breakdown_strategy must be 'page' or 'document', "
                f"got {breakdown_strategy!r}"
            )
        self._mode = mode
        self._endpoint = endpoint
        self._breakdown_strategy = breakdown_strategy

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
        if self._mode == "cloud":
            return await self._call_cloud(image)
        return await self._call_local(image)

    async def _call_cloud(self, image: Image) -> OCRResult:
        """Send a PIL image to the Zhipu cloud API via the glmocr SDK.

        Encodes the image as PNG bytes in the calling thread, then offloads
        the blocking network call to a worker thread.

        # TODO: Replace with confirmed SDK signature once glmocr API docs are
        # finalised. Current stub: glmocr.ocr(image_bytes) -> dict
        """
        import io

        buf = io.BytesIO()
        await asyncio.to_thread(image.save, buf, format="PNG")
        image_bytes = buf.getvalue()
        raw: dict = await asyncio.to_thread(glmocr.ocr, image_bytes)
        return _parse_glmocr_response(raw)

    async def _call_local(self, image: Image) -> OCRResult:
        """POST a PIL image to a local vLLM/Ollama endpoint.

        Sends the image as a base64-encoded PNG in a JSON body and reads the
        response with ``httpx.AsyncClient`` so the event loop is not blocked.

        # TODO: Confirm local endpoint request/response schema once a reference
        # implementation is published.
        """
        import base64
        import io

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

    async def _stream_image(self, path: Path) -> AsyncGenerator[Document, None]:
        """Yield a single Document from one image file."""
        from PIL import Image as PILImage

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

    async def _stream_dir(self) -> AsyncGenerator[Document, None]:
        """Stream Documents from a directory of image files.

        Handles both breakdown strategies so ``astream()`` stays simple.
        """
        image_paths = sorted(
            p
            for p in self._path.rglob("*")
            if p.is_file() and p.suffix.lower() in _SUPPORTED_IMAGE_SUFFIXES
        )
        if self._breakdown_strategy == "document":
            page_texts: list[str] = []
            all_bboxes: list[dict] = []
            all_tables: list[dict] = []
            for path in image_paths:
                async for doc in self._stream_image(path):
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
        for path in image_paths:
            async for doc in self._stream_image(path):
                yield doc

    async def astream(self) -> AsyncGenerator[Document, None]:
        """Stream Documents from image files using GLM-OCR.

        For the ``page`` strategy, yields one ``Document`` per non-empty image
        as soon as it is processed. For the ``document`` strategy, yields one
        ``Document`` per directory after all images are collected.

        If initialised with a directory, iterates all supported image files in
        sorted order (recursively).

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
        if self._path.suffix.lower() not in _SUPPORTED_IMAGE_SUFFIXES:
            raise ValueError(
                f"GLMOCRLoader expects an image file "
                f"({', '.join(sorted(_SUPPORTED_IMAGE_SUFFIXES))}), "
                f"got {self._path.suffix!r}"
            )
        async for doc in self._stream_image(self._path):
            yield doc


class GLMOCRPDFLoader(GLMOCRLoader):
    """Like ``GLMOCRLoader`` but sends PDF bytes straight to GLM-OCR.

    When the GLM-OCR API accepts raw PDF input, rasterizing pages with
    pypdfium2 is unnecessary: the model can process the full PDF in one call
    and return layout-aware output (headings, tables, column order) that would
    be degraded after rasterization. This subclass replaces ``astream()`` to
    read each PDF as raw bytes and delegate to :meth:`_ocr_pdf_structured`
    instead of the PIL-image path.

    The inherited ``_ocr_image`` / ``_ocr_image_structured`` methods remain
    available and can be used as an image-based fallback if needed.

    Note: within a single PDF, GLM-OCR returns the entire document as one blob,
    so sub-page splitting is not available without rasterization. The
    ``breakdown_strategy`` parameter controls *directory-level* aggregation only:
    ``"page"`` yields one ``Document`` per PDF file; ``"document"`` merges all
    PDFs in a directory into one ``Document``.

    Args:
        file_path: Path to a ``.pdf`` file or a directory of ``.pdf`` files.
        mode: Deployment mode — ``"cloud"`` or ``"local"``. Defaults to
            ``"cloud"``.
        endpoint: Base URL of the local OCR endpoint. Required when
            ``mode="local"``.
        breakdown_strategy: Controls directory-level aggregation. Defaults to
            ``"page"``.

    Raises:
        FileNotFoundError: If ``file_path`` does not exist (raised from
            ``astream()``).
        ValueError: If ``file_path`` points to a non-PDF file (raised from
            ``astream()``).
    """

    async def _ocr_pdf_structured(self, pdf_bytes: bytes) -> OCRResult:
        """Send raw PDF bytes to GLM-OCR and return structured output."""
        if self._mode == "cloud":
            return await self._call_cloud_pdf(pdf_bytes)
        return await self._call_local_pdf(pdf_bytes)

    async def _call_cloud_pdf(self, pdf_bytes: bytes) -> OCRResult:
        """Send PDF bytes to the Zhipu cloud API.

        # TODO: Confirm whether the SDK accepts raw bytes or requires base64,
        # and whether format="pdf" is the correct flag. Replace the stub call
        # once the glmocr SDK docs cover PDF input.
        """
        raw: dict = await asyncio.to_thread(glmocr.ocr, pdf_bytes, format="pdf")
        return _parse_glmocr_response(raw)

    async def _call_local_pdf(self, pdf_bytes: bytes) -> OCRResult:
        """POST PDF bytes (base64-encoded) to the local endpoint.

        # TODO: Confirm local endpoint schema for PDF input. Current stub
        # mirrors the image path with "pdf" as the key and format flag.
        """
        import base64

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

    async def _stream_dir(self) -> AsyncGenerator[Document, None]:
        """Stream Documents from a directory of PDF files.

        Handles both breakdown strategies so ``astream()`` stays simple.
        """
        pdf_paths = sorted(p for p in self._path.rglob("*.pdf") if p.is_file())
        if self._breakdown_strategy == "document":
            page_texts: list[str] = []
            all_bboxes: list[dict] = []
            all_tables: list[dict] = []
            for path in pdf_paths:
                async for doc in self._stream_pdf(path):
                    page_texts.append(doc.content)
                    all_bboxes.extend(doc.metadata.get("bboxes", []))
                    all_tables.extend(doc.metadata.get("tables", []))
            if page_texts:
                yield Document(
                    content="\n\n".join(page_texts),
                    type=DocumentType.PDF,
                    source=str(self._path),
                    metadata={"bboxes": all_bboxes, "tables": all_tables},
                )
            return
        for path in pdf_paths:
            async for doc in self._stream_pdf(path):
                yield doc

    async def astream(self) -> AsyncGenerator[Document, None]:
        """Stream Documents from PDF files using GLM-OCR's native PDF support.

        Yields one ``Document`` per PDF file for the ``page`` strategy, or one
        ``Document`` per directory (PDFs joined by ``\\n\\n``) for the
        ``document`` strategy.

        Yields:
            Document: The next extracted document.

        Raises:
            FileNotFoundError: If the path does not exist.
            ValueError: If the path points to a file that is not a ``.pdf``.
        """
        if self._path.is_dir():
            async for doc in self._stream_dir():
                yield doc
            return
        if not self._path.is_file():
            raise FileNotFoundError(f"File not found: {self._path}")
        if self._path.suffix.lower() != ".pdf":
            raise ValueError(
                f"GLMOCRPDFLoader expects a .pdf file, got {self._path.suffix!r}"
            )
        async for doc in self._stream_pdf(self._path):
            yield doc
