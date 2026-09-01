from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from railtracks.retrieval.loaders.base import BaseDocumentLoader
from railtracks.retrieval.models import OCRResult

if TYPE_CHECKING:
    from PIL.Image import Image


class BaseOCRLoader(BaseDocumentLoader):
    """Abstract base for loaders that use OCR to extract text from images.

    Concrete subclasses are responsible for two things:

    1. **Sourcing images.** A PDF loader rasterizes pages; an image-folder
       loader iterates files; a cloud loader fetches scans from a bucket.
       This logic belongs in the subclass's `astream()` implementation.
    2. **OCR'ing an image.** The actual recognition step is delegated to
       `_ocr_image()`, which subclasses implement using their chosen engine
       (Tesseract, EasyOCR, AWS Textract, etc.).

    Splitting the responsibilities this way means a new OCR engine can be
    plugged in without rewriting the source-handling code, and a new source
    can reuse an existing engine via mixin or composition.
    """

    @abstractmethod
    async def _ocr_image(self, image: Image) -> str:
        """OCR a single image into text.

        Args:
            image: The PIL image to recognize text from.

        Returns:
            The extracted text. May be an empty string if no text was found.
        """
        ...

    async def _ocr_image_structured(self, image: Image) -> OCRResult:
        """OCR a single image into structured output.

        Default implementation delegates to :meth:`_ocr_image` and wraps the
        plain-text result in an :class:`~railtracks.retrieval.models.OCRResult`.
        Subclasses that can produce richer output (bounding boxes, tables,
        markdown layout) should override this method directly.

        Args:
            image: The PIL image to recognize text from.

        Returns:
            An :class:`~railtracks.retrieval.models.OCRResult` whose ``markdown``
            field contains the extracted text. ``bboxes`` and ``tables`` are
            empty unless the method is overridden.
        """
        text = await self._ocr_image(image)
        return OCRResult(markdown=text)
