from __future__ import annotations

from pathlib import Path
from typing import Literal

from railtracks.retrieval.loaders.base import BaseDocumentLoader
from railtracks.retrieval.models import Document, DocumentType

try:
    from pypdf import PdfReader
except ImportError as exc:
    raise ImportError(
        "pypdf is required for PyPDFLoader. "
        'Install it with: pip install "railtracks[pdf]"'
    ) from exc


BreakdownStrategy = Literal["page", "document"]


class PyPDFLoader(BaseDocumentLoader):
    """Loads PDF files, splitting them into Documents by page or as a whole.

    If `file_path` points to a directory, all `.pdf` files are loaded
    recursively. If it points to a file, that file is loaded.

    Breakdown strategies:

    - `"page"` *(default)*: one Document per page. `metadata` includes
      `page` (1-based), `total_pages`, and `file_type`.
    - `"document"`: entire PDF as one Document, pages joined by `"\\n\\n"`. 
        `metadata` includes `total_pages` and `file_type`.

    Requires: `pip install "railtracks[pdf]"`


    Args:
        file_path: Path to a `.pdf` file or directory.
        breakdown_strategy: How to split the PDF into Documents.
            Defaults to `"page"`.
    """

    def __init__(
        self,
        file_path: str,
        breakdown_strategy: BreakdownStrategy = "page",
    ) -> None:
        self._path = Path(file_path)
        if breakdown_strategy not in ("page", "document"):
            raise ValueError(
                f"breakdown_strategy must be 'page' or 'document', got {breakdown_strategy!r}"
            )
        self._breakdown_strategy = breakdown_strategy

    def _load_file(self, path: Path) -> list[Document]:
        reader = PdfReader(str(path))
        total_pages = len(reader.pages)
        source = str(path)
        documents: list[Document] = []

        if self._breakdown_strategy == "document":
            content = "\n\n".join(page.extract_text() or "" for page in reader.pages)
            documents.append(
                Document(
                    content=content,
                    type=DocumentType.PDF,
                    source=source,
                    metadata={"total_pages": total_pages, "file_type": ".pdf"},
                )
            )
        else:
            for page_number, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                if not text.strip():
                    continue
                documents.append(
                    Document(
                        content=text,
                        type=DocumentType.PDF,
                        source=source,
                        metadata={
                            "page": page_number,
                            "total_pages": total_pages,
                            "file_type": ".pdf",
                        },
                    )
                )

        return documents

    def load(self) -> list[Document]:
        if self._path.is_dir():
            docs: list[Document] = []
            for p in sorted(self._path.rglob("*.pdf")):
                if p.is_file():
                    docs.extend(self._load_file(p))
            return docs

        if not self._path.is_file():
            raise FileNotFoundError(f"File not found: {self._path}")
        if self._path.suffix.lower() != ".pdf":
            raise ValueError(
                f"PyPDFLoader expects a .pdf file, got {self._path.suffix!r}"
            )

        return self._load_file(self._path)