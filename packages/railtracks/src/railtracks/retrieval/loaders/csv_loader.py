from __future__ import annotations

import csv
from pathlib import Path

from railtracks.retrieval.loaders.base import BaseDocumentLoader
from railtracks.retrieval.models import Document, DocumentType


class CSVLoader(BaseDocumentLoader):
    """Loads CSV files, converting each row into a Document.

    If `file_path` points to a directory, all `.csv` files are loaded
    recursively. If it points to a file, that file is loaded.

    Note on column handling:
    - `content_columns`: values are concatenated (via `content_separator`)
      to form `Document.content`. When `None`, all columns are used.
    - `ignore_columns`: columns dropped entirely — not content, not metadata.
    - Every remaining column (not in `content_columns`, not in
      `ignore_columns`) is added to `Document.metadata`.

    Args:
        file_path: Path to a `.csv` file or directory.
        content_columns: Ordered list of columns to concatenate into `Document.content`.
            `None` means all columns.
        ignore_columns: Columns to drop entirely.
        content_separator: String used to join multiple content-column values.
        encoding: File encoding (default `utf-8-sig`).
    """

    def __init__(
        self,
        file_path: str,
        content_columns: list[str] | None = None,
        ignore_columns: list[str] | None = None,
        content_separator: str = "\n",
        encoding: str = "utf-8-sig",
    ) -> None:
        self._path = Path(file_path)
        self._content_columns = content_columns
        self._ignore_columns = set(ignore_columns or [])
        self._content_separator = content_separator
        self._encoding = encoding

    def _load_file(self, path: Path) -> list[Document]:
        documents: list[Document] = []

        with path.open(encoding=self._encoding, newline="") as f:
            reader = csv.DictReader(f)

            if reader.fieldnames is None:
                return documents

            fieldnames = list(reader.fieldnames)
            content_columns = self._content_columns if self._content_columns is not None else fieldnames

            unknown = [c for c in content_columns if c not in fieldnames]
            if unknown:
                raise ValueError(f"content_columns not found in CSV headers: {unknown}")

            content_col_set = set(content_columns)

            for row_index, row in enumerate(reader):
                content = self._content_separator.join(
                    f"{col}: {row[col]}" for col in content_columns
                )
                metadata = {
                    col: row[col]
                    for col in fieldnames
                    if col not in content_col_set and col not in self._ignore_columns
                }
                metadata["row_index"] = row_index

                documents.append(
                    Document(
                        content=content,
                        type=DocumentType.CSV,
                        source=str(path),
                        metadata=metadata,
                    )
                )

        return documents

    def load(self) -> list[Document]:
        if self._path.is_dir():
            docs: list[Document] = []
            for p in sorted(self._path.rglob("*.csv")):
                if p.is_file():
                    docs.extend(self._load_file(p))
            return docs

        if not self._path.is_file():
            raise FileNotFoundError(f"File not found: {self._path}")
        if self._path.suffix.lower() != ".csv":
            raise ValueError(
                f"CSVLoader expects a .csv file, got {self._path.suffix!r}"
            )

        return self._load_file(self._path)