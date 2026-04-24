from __future__ import annotations

from pathlib import Path

from railtracks.retrieval.loaders.base import BaseDocumentLoader
from railtracks.retrieval.models import Document

_SUPPORTED_EXTENSIONS = {".txt", ".md"}


class TextLoader(BaseDocumentLoader):
    """Loads `.txt` and `.md` files as Documents.

    If `file_path` points to a directory, all `.txt` and `.md` files
    are loaded recursively. If it points to a file, that file is loaded.

    Args:
        file_path: Path to a file or directory.
        encoding: File encoding (default `utf-8`).
    """

    def __init__(self, file_path: str, encoding: str = "utf-8") -> None:
        self._path = Path(file_path)
        self._encoding = encoding

    def _load_file(self, path: Path) -> Document:
        content = path.read_text(encoding=self._encoding)
        doc_type = "markdown" if path.suffix.lower() == ".md" else "text"
        return Document(
            content=content,
            type=doc_type,
            source=str(path),
            metadata={
                "file_type": path.suffix.lower(),
                "encoding": self._encoding,
            },
        )

    def load(self) -> list[Document]:
        if self._path.is_dir():
            return [
                self._load_file(p)
                for p in sorted(self._path.rglob("*"))
                if p.suffix.lower() in _SUPPORTED_EXTENSIONS and p.is_file()
            ]

        if self._path.suffix.lower() not in _SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file extension: {self._path.suffix!r}. "
                f"Supported extensions: {_SUPPORTED_EXTENSIONS}"
            )
        if not self._path.is_file():
            raise FileNotFoundError(f"File not found: {self._path}")

        return [self._load_file(self._path)]
