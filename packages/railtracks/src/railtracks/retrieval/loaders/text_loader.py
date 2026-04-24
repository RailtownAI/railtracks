from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path

from railtracks.retrieval.loaders.base import BaseDocumentLoader
from railtracks.retrieval.models import Document, DocumentType

_SUPPORTED_EXTENSIONS = {".txt", ".md"}


class TextLoader(BaseDocumentLoader):
    """Loads `.txt` and `.md` files as `Document` objects.

    If `file_path` points to a directory, all `.txt` and `.md` files
    are loaded recursively in sorted order. If it points to a file,
    that file is loaded.

    Each file is read and yielded individually as soon as it is ready,
    allowing downstream stages to begin processing without waiting for
    the full corpus to load.

    Args:
        file_path: Path to a `.txt` or `.md` file, or a directory
            containing such files.
        encoding: File encoding. Defaults to `utf-8-sig`.

    Raises:
        FileNotFoundError: If `file_path` does not exist.
        ValueError: If `file_path` points to a file with an unsupported
            extension.
    """

    def __init__(self, file_path: str, encoding: str = "utf-8-sig") -> None:
        self._path = Path(file_path)
        self._encoding = encoding

    def _load_file(self, path: Path) -> Document:
        """Read a single file and return it as a `Document`.

        Args:
            path: Path to the file to read.

        Returns:
            Document: The loaded document.
        """
        content = path.read_text(encoding=self._encoding)
        doc_type = DocumentType.MARKDOWN if path.suffix.lower() == ".md" else DocumentType.TEXT
        return Document(
            content=content,
            type=doc_type,
            source=str(path),
            metadata={
                "file_type": path.suffix.lower(),
                "encoding": self._encoding,
            },
        )

    async def astream(self) -> AsyncGenerator[Document, None]:
        """Stream documents one at a time as each file is read.

        If initialised with a directory, yields one `Document` per file
        in sorted order. If initialised with a single file, yields one
        `Document`.

        Yields:
            Document: The next loaded document.

        Raises:
            FileNotFoundError: If the path does not exist.
            ValueError: If the path points to a file with an unsupported
                extension.
        """
        if self._path.is_dir():
            paths = sorted(
                p for p in self._path.rglob("*")
                if p.suffix.lower() in _SUPPORTED_EXTENSIONS and p.is_file()
            )
            for path in paths:
                yield await asyncio.to_thread(self._load_file, path)
            return

        if self._path.suffix.lower() not in _SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file extension: {self._path.suffix!r}. "
                f"Supported extensions: {_SUPPORTED_EXTENSIONS}"
            )
        if not self._path.is_file():
            raise FileNotFoundError(f"File not found: {self._path}")

        yield await asyncio.to_thread(self._load_file, self._path)