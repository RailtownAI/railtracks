from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

# Skip the whole module if Pillow is not installed — tests that exercise
# _stream_image reach PIL.Image.open via patch; the target must resolve.
pytest.importorskip("PIL")

# Stub glmocr before the loader module is imported — the module-level
# `import glmocr` re-raises ImportError if the package is missing, which
# would prevent collection. The real SDK is not required for unit tests.
if "glmocr" not in sys.modules:
    sys.modules["glmocr"] = MagicMock()

from railtracks.retrieval.loaders.glm_ocr_loader import GLMOCRLoader  # noqa: E402
from railtracks.retrieval.models import OCRResult  # noqa: E402

_FAKE_RESPONSE = {
    "markdown": "# Hello\n\nWorld",
    "bboxes": [{"x": 0, "y": 0, "w": 100, "h": 20}],
    "tables": [{"rows": [["cell"]]}],
}


def _make_image() -> MagicMock:
    """Return a minimal PIL Image stand-in."""
    return MagicMock()


async def _fake_to_thread(func, *args, **kwargs):
    """Drop-in for asyncio.to_thread that executes func in the calling thread."""
    return func(*args, **kwargs)


class TestGLMOCRLoaderInit:
    """Tests for GLMOCRLoader construction and parameter validation."""

    def test_default_breakdown_strategy_is_page(self, tmp_path):
        loader = GLMOCRLoader(str(tmp_path / "img.png"))
        assert loader._breakdown_strategy == "page"

    def test_invalid_breakdown_strategy_raises_value_error(self, tmp_path):
        with pytest.raises(ValueError, match="breakdown_strategy"):
            GLMOCRLoader(
                str(tmp_path / "img.png"),
                breakdown_strategy="chapter",  # type: ignore[arg-type]
            )

    def test_strategy_cloud_inferred_when_no_endpoint(self):
        loader = GLMOCRLoader(file_path="test.png")
        assert loader._call == loader._call_cloud
        assert loader._call_pdf == loader._call_cloud_pdf

    def test_strategy_local_inferred_when_endpoint_provided(self):
        loader = GLMOCRLoader(file_path="test.png", endpoint="http://localhost:8080")
        assert loader._call == loader._call_local
        assert loader._call_pdf == loader._call_local_pdf

    def test_pdf_detected_from_extension(self):
        assert GLMOCRLoader(file_path="doc.pdf")._is_pdf is True
        assert GLMOCRLoader(file_path="img.png")._is_pdf is False

    def test_invalid_endpoint_raises_value_error(self):
        with pytest.raises(ValueError, match="endpoint"):
            GLMOCRLoader(file_path="x.png", endpoint="")


class TestGLMOCRLoaderErrors:
    """Tests for file-access error conditions raised from astream()."""

    async def test_missing_file_raises_file_not_found(self, tmp_path):
        loader = GLMOCRLoader(str(tmp_path / "ghost.png"))
        with pytest.raises(FileNotFoundError):
            await loader.aload()

    async def test_unsupported_extension_raises_value_error(self, tmp_path):
        f = tmp_path / "data.txt"
        f.write_text("not an image", encoding="utf-8")
        loader = GLMOCRLoader(str(f))
        with pytest.raises(ValueError, match="GLMOCRLoader expects an image or PDF file"):
            await loader.aload()


class TestGLMOCRLoaderPageStrategy:
    """The 'page' strategy (default) yields one Document per image file."""

    async def test_directory_yields_one_document_per_image(self, tmp_path):
        (tmp_path / "a.png").touch()
        (tmp_path / "b.png").touch()
        loader = GLMOCRLoader(str(tmp_path))
        with (
            patch("railtracks.retrieval.loaders.glm_ocr_loader.glmocr") as mock_glmocr,
            patch("asyncio.to_thread", new=_fake_to_thread),
            patch("PIL.Image.open", return_value=_make_image()),
        ):
            mock_glmocr.ocr.return_value = _FAKE_RESPONSE
            docs = await loader.aload()
        assert len(docs) == 2

    async def test_directory_ignores_non_image_files(self, tmp_path):
        (tmp_path / "doc.png").touch()
        (tmp_path / "readme.txt").write_text("text", encoding="utf-8")
        loader = GLMOCRLoader(str(tmp_path))
        with (
            patch("railtracks.retrieval.loaders.glm_ocr_loader.glmocr") as mock_glmocr,
            patch("asyncio.to_thread", new=_fake_to_thread),
            patch("PIL.Image.open", return_value=_make_image()),
        ):
            mock_glmocr.ocr.return_value = _FAKE_RESPONSE
            docs = await loader.aload()
        assert len(docs) == 1

    async def test_empty_directory_returns_empty_list(self, tmp_path):
        docs = await GLMOCRLoader(str(tmp_path)).aload()
        assert docs == []


class TestGLMOCRLoaderDocumentStrategy:
    """The 'document' strategy merges all images in a directory into one Document."""

    async def test_yields_one_document_for_directory(self, tmp_path):
        (tmp_path / "a.png").touch()
        (tmp_path / "b.png").touch()
        loader = GLMOCRLoader(str(tmp_path), breakdown_strategy="document")
        with (
            patch("railtracks.retrieval.loaders.glm_ocr_loader.glmocr") as mock_glmocr,
            patch("asyncio.to_thread", new=_fake_to_thread),
            patch("PIL.Image.open", return_value=_make_image()),
        ):
            mock_glmocr.ocr.return_value = _FAKE_RESPONSE
            docs = await loader.aload()
        assert len(docs) == 1

    async def test_pages_joined_with_double_newline(self, tmp_path):
        (tmp_path / "a.png").touch()
        (tmp_path / "b.png").touch()
        markdown = "page content"
        loader = GLMOCRLoader(str(tmp_path), breakdown_strategy="document")
        with (
            patch("railtracks.retrieval.loaders.glm_ocr_loader.glmocr") as mock_glmocr,
            patch("asyncio.to_thread", new=_fake_to_thread),
            patch("PIL.Image.open", return_value=_make_image()),
        ):
            mock_glmocr.ocr.return_value = {
                "markdown": markdown,
                "bboxes": [],
                "tables": [],
            }
            docs = await loader.aload()
        assert docs[0].content == f"{markdown}\n\n{markdown}"


class TestOCRResult:
    """Tests for the OCRResult dataclass (public API surface)."""

    def test_to_text_returns_markdown(self):
        """OCRResult.to_text() must return the markdown field verbatim."""
        result = OCRResult(markdown="# Hello")
        assert result.to_text() == "# Hello"

    def test_bboxes_defaults_to_empty_list(self):
        result = OCRResult(markdown="text")
        assert result.bboxes == []

    def test_tables_defaults_to_empty_list(self):
        result = OCRResult(markdown="text")
        assert result.tables == []


class TestMissingDependency:
    """The loader module must raise ImportError with an install hint if glmocr is absent."""

    def test_missing_glmocr_raises_import_error_with_install_hint(self):
        import importlib

        loader_key = "railtracks.retrieval.loaders.glm_ocr_loader"
        saved_glmocr = sys.modules.pop("glmocr", None)
        saved_loader = sys.modules.pop(loader_key, None)
        try:
            with pytest.raises(ImportError, match=r"railtracks\[glm\]"):
                importlib.import_module(loader_key)
        finally:
            if saved_glmocr is not None:
                sys.modules["glmocr"] = saved_glmocr
            if saved_loader is not None:
                sys.modules[loader_key] = saved_loader
