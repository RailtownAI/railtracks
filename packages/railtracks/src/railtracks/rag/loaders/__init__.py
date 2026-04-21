from railtracks.rag.loaders.base import BaseDocumentLoader
from railtracks.rag.loaders.code_loader import EXTENSION_TO_LANGUAGE, CodeLoader
from railtracks.rag.loaders.csv_loader import CSVLoader

from railtracks.rag.loaders.langchain_adapter import LangChainLoaderAdapter
from railtracks.rag.loaders.text_loader import TextLoader

# Optional-dep loaders are importable directly from their modules:
#   from railtracks.rag.loaders.pdf_loader import PDFLoader
#   from railtracks.rag.loaders.html_loader import HTMLLoader
#   from railtracks.rag.loaders.docx_loader import DocxLoader

__all__ = [
    "BaseDocumentLoader",
    "CodeLoader",
    "CSVLoader",
    "EXTENSION_TO_LANGUAGE",
    "LangChainLoaderAdapter",
    "TextLoader",
]
