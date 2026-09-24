from typing import TYPE_CHECKING

from railtracks.retrieval.loaders.base import BaseDocumentLoader
from railtracks.retrieval.loaders.base_ocr import BaseOCRLoader
from railtracks.retrieval.loaders.cloud import (
    AzureBlobLoader,
    GCSLoader,
    S3Loader,
    SQLLoader,
)
from railtracks.retrieval.loaders.csv_loader import CSVLoader
from railtracks.retrieval.loaders.json_loader import JSONLoader
from railtracks.retrieval.loaders.langchain_loader import LangChainLoaderAdapter
from railtracks.retrieval.loaders.sanitizing import Sanitizer, SanitizingLoader
from railtracks.retrieval.loaders.text_loader import TextLoader
from railtracks.retrieval.models import DocumentType

if TYPE_CHECKING:
    from railtracks.retrieval.loaders.huggingface_loader import HuggingFaceDatasetLoader
    from railtracks.retrieval.loaders.pdf_loader import PyPDFLoader
    from railtracks.retrieval.loaders.pdf_ocr_loader import PyPDFOCRLoader

__all__ = [
    "AzureBlobLoader",
    "BaseDocumentLoader",
    "BaseOCRLoader",
    "CSVLoader",
    "DocumentType",
    "GCSLoader",
    "HuggingFaceDatasetLoader",
    "JSONLoader",
    "LangChainLoaderAdapter",
    "PyPDFLoader",
    "PyPDFOCRLoader",
    "S3Loader",
    "SQLLoader",
    "Sanitizer",
    "SanitizingLoader",
    "TextLoader",
]


def __getattr__(name: str):
    if name == "PyPDFLoader":
        from railtracks.retrieval.loaders.pdf_loader import PyPDFLoader

        return PyPDFLoader
    elif name == "HuggingFaceDatasetLoader":
        from railtracks.retrieval.loaders.huggingface_loader import (
            HuggingFaceDatasetLoader,
        )

        return HuggingFaceDatasetLoader
    elif name == "PyPDFOCRLoader":
        from railtracks.retrieval.loaders.pdf_ocr_loader import PyPDFOCRLoader

        return PyPDFOCRLoader
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
