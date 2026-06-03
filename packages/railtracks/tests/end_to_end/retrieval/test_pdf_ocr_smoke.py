"""End-to-end smoke test for PyPDFOCRLoader.

Exercises the full OCR chain against real binaries:

    Pillow (synthesize scanned PDF) → pypdfium2 (rasterize) → Tesseract (OCR)

Excluded from regular CI: the `end_to_end/retrieval` directory is ignored
in the workspace `pyproject.toml`'s `addopts`, so this only runs when
invoked explicitly. It requires:

    1. `pip install "railtracks[ocr]"` for the Python OCR libs
    2. The Tesseract binary installed and on PATH

Run manually with:

    uv run pytest packages/railtracks/tests/end_to_end/retrieval/test_pdf_ocr_smoke.py -v -s
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont
from railtracks.retrieval.loaders.pdf_ocr_loader import PyPDFOCRLoader

pytestmark = pytest.mark.integration


def _try_load_font(size: int):
    """Pick a clear truetype font; fall back to PIL's bitmap default.

    Tesseract accuracy drops sharply on PIL's tiny default bitmap font, so
    we try common system truetype paths first.
    """
    candidates = [
        "arial.ttf",  # Windows (resolved via system font dirs)
        "Arial.ttf",
        "/Library/Fonts/Arial.ttf",  # macOS
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


@pytest.fixture
def scanned_pdf(tmp_path: Path) -> tuple[Path, str]:
    """Create a synthetic image-only PDF with known text rendered on it.

    Returns (path_to_pdf, expected_text).
    """
    expected_text = "HELLO OCR WORLD"

    # 8.5" x 11" at 300 DPI -> 2550 x 3300 px.
    img = Image.new("RGB", (2550, 3300), color="white")
    draw = ImageDraw.Draw(img)
    font = _try_load_font(120)
    draw.text((300, 1500), expected_text, fill="black", font=font)

    pdf_path = tmp_path / "scanned.pdf"
    img.save(pdf_path, "PDF", resolution=300.0)

    return pdf_path, expected_text


class TestPyPDFOCRLoaderSmoke:
    """Real binaries: Pillow generates, pypdfium2 rasterizes, Tesseract OCRs."""

    async def test_ocr_recovers_text_from_image_only_pdf(self, scanned_pdf):
        """The hybrid path should detect no text layer and fall back to OCR."""
        pdf_path, expected_text = scanned_pdf
        docs = await PyPDFOCRLoader(str(pdf_path)).aload()

        assert len(docs) == 1, "Synthetic single-page PDF should yield one Document"
        assert docs[0].metadata["ocr"] is True, (
            "Image-only PDF should have triggered OCR fallback, not text extraction"
        )

        # Tesseract may add/drop whitespace or misrecognize edge characters,
        # so assert word-by-word rather than equality.
        recovered = docs[0].content.upper()
        for word in expected_text.split():
            assert word in recovered, (
                f"Expected word {word!r} not found in OCR output: {docs[0].content!r}"
            )

    async def test_force_ocr_produces_same_result(self, scanned_pdf):
        """Setting force_ocr=True should still recover the text."""
        pdf_path, expected_text = scanned_pdf
        docs = await PyPDFOCRLoader(str(pdf_path), force_ocr=True).aload()

        assert len(docs) == 1
        assert docs[0].metadata["ocr"] is True
        recovered = docs[0].content.upper()
        for word in expected_text.split():
            assert word in recovered
