# pdf_loader.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from railtracks.retrieval.loaders.base import BaseDocumentLoader
from railtracks.retrieval.models import Document

BreakdownStrategy = Literal["page", "document"]


class PDFLoader(BaseDocumentLoader):
    """Loads a PDF file, yielding Documents according to `breakdown_strategy`.

    Each strategy controls how the PDF is split into Documents:

    - `"page"`: one Document per page (default).
    - `"document"`: entire PDF as one Document.

    Metadata always includes `source`. Page-level strategy also includes
    `page` (0-based) and `total_pages`.

    Note:
        Embedded images are not extracted. `pdfplumber` exposes image
        position and name metadata but not pixel content, so there is no
        meaningful text to include. Full image support (OCR via
        `pytesseract` or vision-model captioning) is deferred until
        multi-modal support is added to the framework.

        Paragraph-level splitting is intentionally omitted. PDF text layers
        rarely preserve double-newline paragraph boundaries reliably.
        Paragraph-level granularity is better achieved downstream via
        `RecursiveChunker`.

    Requires:
        `pip install "railtracks[pdf]"`

    Args:
        file_path: Path to a `.pdf` file or directory. When a directory
            is provided, all `.pdf` files are loaded recursively.
        breakdown_strategy: How to split the PDF into Documents.
            Defaults to `"page"`.
        password: Decryption password for password-protected PDFs.
    """

    def __init__(
        self,
        file_path: str,
        breakdown_strategy: BreakdownStrategy = "page",
        password: str | None = None,
    ) -> None:
        self._path = Path(file_path)
        self._breakdown_strategy = breakdown_strategy
        self._password = password

    def _extract_page_content(self, page: Any) -> str:
        """Extract text content from a single pdfplumber page.

        Args:
            page: A `pdfplumber.Page` instance.

        Returns:
            Extracted text, or an empty string if the page has no text layer.
        """
        return page.extract_text() or ""

    def _load_file(self, path: Path) -> list[Document]:
        """Load Documents from a single PDF file.

        Args:
            path: Resolved path to a `.pdf` file.

        Returns:
            A list of Documents split according to `breakdown_strategy`.

        Raises:
            ImportError: If `pdfplumber` is not installed.
        """
        try:
            import pdfplumber
        except ImportError:
            raise ImportError(
                'pdfplumber is required for PDFLoader. '
                'Install it with: pip install "railtracks[pdf]"'
            )

        source = str(path)
        documents: list[Document] = []

        with pdfplumber.open(path, password=self._password) as pdf:
            total_pages = len(pdf.pages)

            if self._breakdown_strategy == "document":
                content = "\n\n".join(
                    self._extract_page_content(page)
                    for page in pdf.pages
                )
                documents.append(
                    Document(
                        content=content,
                        source=source,
                        metadata={"total_pages": total_pages},
                    )
                )

            elif self._breakdown_strategy == "page":
                for page in pdf.pages:
                    documents.append(
                        Document(
                            content=self._extract_page_content(page),
                            source=source,
                            metadata={
                                "page": page.page_number - 1,
                                "total_pages": total_pages,
                            },
                        )
                    )

        return documents

    def load(self) -> list[Document]:
        """Load Documents from the configured path.

        If `file_path` is a directory, all `.pdf` files are loaded
        recursively in sorted order.

        Returns:
            A list of Documents split according to `breakdown_strategy`.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file does not have a `.pdf` extension.
            ImportError: If `pdfplumber` is not installed.
        """
        if self._path.is_dir():
            docs: list[Document] = []
            for p in sorted(self._path.rglob("*.pdf")):
                if p.is_file():
                    docs.extend(self._load_file(p))
            return docs

        if self._path.suffix.lower() != ".pdf":
            raise ValueError(
                f"PDFLoader expects a .pdf file, got {self._path.suffix!r}"
            )
        if not self._path.is_file():
            raise FileNotFoundError(f"File not found: {self._path}")

        return self._load_file(self._path)