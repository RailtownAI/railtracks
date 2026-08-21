from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

# Stub glmocr before the loader module is imported — it is imported at module
# level and will re-raise ImportError if absent, preventing collection.
if "glmocr" not in sys.modules:
    sys.modules["glmocr"] = MagicMock()

from railtracks.retrieval.loaders.glm_ocr_loader import (  # noqa: E402
    CloudOCRStrategy,
    GLMOCRLoader,
    LocalOCRStrategy,
)
from railtracks.retrieval.models import OCRResult  # noqa: E402


def _make_pipeline_result(markdown: str = "# Hello\n\nWorld") -> MagicMock:
    """Return a minimal PipelineResult stand-in."""
    result = MagicMock()
    result.markdown_result = markdown
    result.to_dict.return_value = {
        "markdown_result": markdown,
        "json_result": {"pages": []},
        "original_images": [],
    }
    return result


async def _fake_to_thread(func, *args, **kwargs):
    """Drop-in for asyncio.to_thread that runs func synchronously."""
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

    def test_cloud_strategy_selected_when_no_endpoint(self):
        loader = GLMOCRLoader(file_path="test.png")
        assert isinstance(loader.strategy, CloudOCRStrategy)

    def test_local_strategy_selected_when_endpoint_provided(self):
        loader = GLMOCRLoader(file_path="test.png", endpoint="http://localhost:8080")
        assert isinstance(loader.strategy, LocalOCRStrategy)

    def test_strategy_can_be_swapped_at_runtime(self):
        loader = GLMOCRLoader(file_path="test.png")
        assert isinstance(loader.strategy, CloudOCRStrategy)
        loader.strategy = LocalOCRStrategy("http://localhost:8080")
        assert isinstance(loader.strategy, LocalOCRStrategy)

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


class TestGLMOCRLoaderOCRDelegation:
    """Tests that OCR methods delegate correctly through the active strategy."""

    async def test_ocr_image_returns_str(self):
        """_ocr_image() must return a plain str (satisfies the abstract contract)."""
        loader = GLMOCRLoader(file_path="test.png")
        pipeline_result = _make_pipeline_result("# Hello\n\nWorld")
        with (
            patch("railtracks.retrieval.loaders.glm_ocr_loader.glmocr") as mock_glmocr,
            patch("asyncio.to_thread", new=_fake_to_thread),
        ):
            mock_glmocr.parse.return_value = pipeline_result
            result = await loader._ocr_image(MagicMock())
        assert isinstance(result, str)

    async def test_ocr_image_structured_returns_ocr_result(self):
        """_ocr_image_structured() must return an OCRResult with markdown populated."""
        loader = GLMOCRLoader(file_path="test.png")
        pipeline_result = _make_pipeline_result("# Hello\n\nWorld")
        with (
            patch("railtracks.retrieval.loaders.glm_ocr_loader.glmocr") as mock_glmocr,
            patch("asyncio.to_thread", new=_fake_to_thread),
        ):
            mock_glmocr.parse.return_value = pipeline_result
            result = await loader._ocr_image_structured(MagicMock())
        assert isinstance(result, OCRResult)
        assert result.markdown == "# Hello\n\nWorld"

    async def test_ocr_image_flattens_structured_output(self):
        """_ocr_image() must return the same text as _ocr_image_structured().to_text()."""
        loader = GLMOCRLoader(file_path="test.png")
        pipeline_result = _make_pipeline_result("# Hello\n\nWorld")
        with (
            patch("railtracks.retrieval.loaders.glm_ocr_loader.glmocr") as mock_glmocr,
            patch("asyncio.to_thread", new=_fake_to_thread),
        ):
            mock_glmocr.parse.return_value = pipeline_result
            text = await loader._ocr_image(MagicMock())
            structured = await loader._ocr_image_structured(MagicMock())
        assert text == structured.to_text()


class TestGLMOCRLoaderPageStrategy:
    """The 'page' strategy (default) yields one Document per image file."""

    async def test_directory_yields_one_document_per_image(self, tmp_path):
        (tmp_path / "a.png").touch()
        (tmp_path / "b.png").touch()
        loader = GLMOCRLoader(str(tmp_path))
        pipeline_result = _make_pipeline_result()
        with (
            patch("railtracks.retrieval.loaders.glm_ocr_loader.glmocr") as mock_glmocr,
            patch("asyncio.to_thread", new=_fake_to_thread),
        ):
            mock_glmocr.parse.return_value = pipeline_result
            docs = await loader.aload()
        assert len(docs) == 2

    async def test_directory_ignores_non_image_files(self, tmp_path):
        (tmp_path / "doc.png").touch()
        (tmp_path / "readme.txt").write_text("text", encoding="utf-8")
        loader = GLMOCRLoader(str(tmp_path))
        pipeline_result = _make_pipeline_result()
        with (
            patch("railtracks.retrieval.loaders.glm_ocr_loader.glmocr") as mock_glmocr,
            patch("asyncio.to_thread", new=_fake_to_thread),
        ):
            mock_glmocr.parse.return_value = pipeline_result
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
        pipeline_result = _make_pipeline_result()
        with (
            patch("railtracks.retrieval.loaders.glm_ocr_loader.glmocr") as mock_glmocr,
            patch("asyncio.to_thread", new=_fake_to_thread),
        ):
            mock_glmocr.parse.return_value = pipeline_result
            docs = await loader.aload()
        assert len(docs) == 1

    async def test_pages_joined_with_double_newline(self, tmp_path):
        (tmp_path / "a.png").touch()
        (tmp_path / "b.png").touch()
        markdown = "page content"
        loader = GLMOCRLoader(str(tmp_path), breakdown_strategy="document")
        pipeline_result = _make_pipeline_result(markdown)
        with (
            patch("railtracks.retrieval.loaders.glm_ocr_loader.glmocr") as mock_glmocr,
            patch("asyncio.to_thread", new=_fake_to_thread),
        ):
            mock_glmocr.parse.return_value = pipeline_result
            docs = await loader.aload()
        assert docs[0].content == f"{markdown}\n\n{markdown}"


class TestOCRResult:
    """Tests for the OCRResult dataclass (public API surface)."""

    def test_to_text_returns_markdown(self):
        result = OCRResult(markdown="# Hello")
        assert result.to_text() == "# Hello"

    def test_json_result_defaults_to_none(self):
        result = OCRResult(markdown="text")
        assert result.json_result is None


class TestMissingDependency:
    """The loader module must raise ImportError with an install hint if glmocr is absent."""

    def test_missing_glmocr_raises_import_error_with_install_hint(self):
        import importlib

        loader_key = "railtracks.retrieval.loaders.glm_ocr_loader"
        saved_glmocr = sys.modules.get("glmocr")
        saved_loader = sys.modules.pop(loader_key, None)
        # Setting a key to None blocks the import regardless of whether the
        # package is physically installed — "import glmocr" raises ImportError.
        sys.modules["glmocr"] = None  # type: ignore[assignment]
        try:
            with pytest.raises(ImportError, match=r"railtracks\[glm\]"):
                importlib.import_module(loader_key)
        finally:
            if saved_glmocr is not None:
                sys.modules["glmocr"] = saved_glmocr
            else:
                sys.modules.pop("glmocr", None)
            if saved_loader is not None:
                sys.modules[loader_key] = saved_loader
