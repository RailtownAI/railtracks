from __future__ import annotations

import asyncio
import tempfile
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, Literal

from railtracks.retrieval.loaders.base_ocr import BaseOCRLoader
from railtracks.retrieval.models import Document, DocumentType, OCRResult

try:
    import glmocr
except ImportError as exc:
    raise ImportError(
        "glmocr is required for GLMOCRLoader. "
        'Install it with: pip install "railtracks[glm]".'
    ) from exc


BreakdownStrategy = Literal["page", "document"]

_SUPPORTED_IMAGE_SUFFIXES = frozenset(
    {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
)
_SUPPORTED_SUFFIXES = _SUPPORTED_IMAGE_SUFFIXES | frozenset({".pdf"})


def _parse_glmocr_response(result: Any) -> OCRResult:
    data = result.to_dict()
    return OCRResult(
        markdown=result.markdown_result or "",
        bboxes=[],
        tables=[],
        json_result=data.get("json_result"),
    )


class GLMOCRStrategy(ABC):
    """Abstract interface for GLM-OCR execution strategies."""

    @abstractmethod
    async def ocr_image(self, path: Path) -> OCRResult: ...

    @abstractmethod
    async def ocr_pdf(self, path: Path) -> OCRResult: ...


class CloudOCRStrategy(GLMOCRStrategy):
    """Delegates OCR to the Zhipu cloud API via glmocr.parse(mode='maas')."""

    async def ocr_image(self, path: Path) -> OCRResult:
        result = await asyncio.to_thread(glmocr.parse, path, mode="maas")
        return _parse_glmocr_response(result)

    async def ocr_pdf(self, path: Path) -> OCRResult:
        result = await asyncio.to_thread(glmocr.parse, path, mode="maas")
        return _parse_glmocr_response(result)


class LocalOCRStrategy(GLMOCRStrategy):
    """Routes OCR to a self-hosted vLLM/SGLang/Ollama endpoint via the SDK."""

    def __init__(self, endpoint: str) -> None:
        self._endpoint = endpoint

    async def ocr_image(self, path: Path) -> OCRResult:
        result = await asyncio.to_thread(
            glmocr.parse, path, mode="selfhosted", api_url=self._endpoint
        )
        return _parse_glmocr_response(result)

    async def ocr_pdf(self, path: Path) -> OCRResult:
        result = await asyncio.to_thread(
            glmocr.parse, path, mode="selfhosted", api_url=self._endpoint
        )
        return _parse_glmocr_response(result)


class GLMOCRLoader(BaseOCRLoader):
    """Loads image and PDF files as ``Document`` objects using GLM-OCR.

    Acts as the Strategy *context*: selects a :class:`GLMOCRStrategy`
    at construction time based on ``endpoint`` and delegates all SDK
    calls through it.

    - ``endpoint=None`` *(default)*: uses :class:`CloudOCRStrategy`
      (Zhipu cloud API, ``mode='maas'``).
    - ``endpoint="https://…"`` (non-empty URL): uses
      :class:`LocalOCRStrategy` (self-hosted vLLM/SGLang/Ollama,
      ``mode='selfhosted'``).

    The active strategy can be swapped at runtime via the
    :attr:`strategy` property setter.

    Handles both file types:

    - **Image files** (``.bmp``, ``.jpeg``, ``.jpg``, ``.png``, ``.tif``,
      ``.tiff``, ``.webp``): passed directly to ``glmocr.parse()`` by path.
    - **PDF files** (``.pdf``): passed directly to ``glmocr.parse()`` by path.
      Format is auto-detected by the SDK from file bytes.

    Breakdown strategies:

    - ``page`` *(default)*: one ``Document`` per file.
    - ``document``: all files in a directory concatenated into one
      ``Document`` with pages joined by ``\\n\\n``.

    Requires:
        ``pip install "railtracks[glm]"``

    Args:
        file_path: Path to an image or PDF file, or a directory of such files.
        endpoint: Full URL of a self-hosted OCR server, or ``None`` to use
            the Zhipu cloud API.
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
        self._strategy: GLMOCRStrategy = (
            CloudOCRStrategy() if endpoint is None else LocalOCRStrategy(endpoint)
        )

    @property
    def strategy(self) -> GLMOCRStrategy:
        """The active OCR strategy; can be replaced at runtime."""
        return self._strategy

    @strategy.setter
    def strategy(self, strategy: GLMOCRStrategy) -> None:
        self._strategy = strategy

    async def _ocr_image(self, image: Any) -> str:
        """Return flat text from a PIL Image (satisfies BaseOCRLoader contract)."""
        result = await self._ocr_image_structured(image)
        return result.to_text()

    async def _ocr_image_structured(self, image: Any) -> OCRResult:
        """OCR a PIL Image by writing it to a temp file and passing the path."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        await asyncio.to_thread(image.save, tmp_path, format="PNG")
        try:
            return await self._strategy.ocr_image(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

    async def _ocr_pdf_structured(self, pdf_bytes: bytes) -> OCRResult:
        """OCR PDF bytes by writing them to a temp file and passing the path."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = Path(tmp.name)
        try:
            return await self._strategy.ocr_pdf(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

    async def _stream_image(self, path: Path) -> AsyncGenerator[Document, None]:
        """Yield a single Document from one image file."""
        result = await self._strategy.ocr_image(path)
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
        """Yield a Document from one PDF file."""
        result = await self._strategy.ocr_pdf(path)
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
        """Stream Documents from a directory of image and PDF files."""
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
