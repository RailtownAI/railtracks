from railtracks.retrieval.loaders.base import BaseDocumentLoader
from railtracks.retrieval.loaders.csv_loader import CSVLoader
from railtracks.retrieval.loaders.json_loader import JSONLoader
from railtracks.retrieval.loaders.text_loader import TextLoader

# Optional-dep loaders are importable directly from their modules:
#   from railtracks.retrieval.loaders.pdf_loader import PyPDFLoader
#   from railtracks.retrieval.loaders.html_loader import HTMLLoader

__all__ = [
    "BaseDocumentLoader",
    "CSVLoader",
    "JSONLoader",
    "TextLoader",
]
