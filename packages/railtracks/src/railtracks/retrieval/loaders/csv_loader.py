from __future__ import annotations

import asyncio
import csv
from collections.abc import AsyncGenerator
from pathlib import Path

from railtracks.retrieval.loaders.base import BaseDocumentLoader
from railtracks.retrieval.models import Document, DocumentType


class CSVLoader(BaseDocumentLoader):
    """Loads CSV files as `Document` objects.

    If `file_path` points to a directory, all `.csv` files are loaded
    recursively in sorted order. If it points to a file, that file is loaded.

    Each row is converted to a `Document` and yielded as soon as it is read,
    without buffering the full file in memory.

    Column handling:

    - `content_columns`: values are concatenated via `content_separator` to
      form `Document.content`. When `None`, all columns are used as content.
    - `ignore_columns`: columns dropped entirely from both content and metadata.
    - Every remaining column (not in `content_columns`, not in
      `ignore_columns`) is added to `Document.metadata`.

    Args:
        file_path: Path to a `.csv` file or a directory containing `.csv`
            files.
        content_columns: Ordered list of columns to concatenate into
            `Document.content`. Defaults to `None`, which uses all columns.
        ignore_columns: Columns to drop entirely from both content and
            metadata.
        content_separator: String used to join multiple content-column values.
            Defaults to `"\\n"`.
        encoding: File encoding. Defaults to `utf-8-sig`.

    Raises:
        FileNotFoundError: If `file_path` does not exist.
        ValueError: If `file_path` points to a file with an unsupported
            extension, or any column in `content_columns` is not found in
            the CSV headers.
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

    async def _stream_file(self, path: Path) -> AsyncGenerator[Document, None]:
        """Stream documents from a single CSV file, one row at a time.

        Args:
            path: Path to the CSV file to read.

        Yields:
            Document: The next row as a document.

        Raises:
            ValueError: If any column in `content_columns` is not found in
                the CSV headers.
        """
        source = str(path)

        def _iter_rows():
            with path.open(encoding=self._encoding, newline="") as f:
                reader = csv.DictReader(f)

                if reader.fieldnames is None:
                    return

                fieldnames = list(reader.fieldnames)
                content_columns = (
                    self._content_columns
                    if self._content_columns is not None
                    else fieldnames
                )

                unknown = [c for c in content_columns if c not in fieldnames]
                if unknown:
                    raise ValueError(
                        f"content_columns not found in CSV headers: {unknown}"
                    )

                content_col_set = set(content_columns)

                for row_index, row in enumerate(reader):
                    content = self._content_separator.join(
                        f"{col}: {row[col]}" for col in content_columns
                    )
                    metadata = {
                        col: row[col]
                        for col in fieldnames
                        if col not in content_col_set
                        and col not in self._ignore_columns
                    }
                    metadata["row_index"] = row_index
                    yield Document(
                        content=content,
                        type=DocumentType.CSV,
                        source=source,
                        metadata=metadata,
                    )

        for doc in await asyncio.to_thread(lambda: list(_iter_rows())):
            yield doc

    async def astream(self) -> AsyncGenerator[Document, None]:
        """Stream documents one at a time as each CSV row is read.

        For a directory, files are streamed in sorted order. Within each
        file, rows are yielded individually without buffering the full file
        in memory.

        Yields:
            Document: The next row as a document.

        Raises:
            FileNotFoundError: If the path does not exist.
            ValueError: If the path points to a file with an unsupported
                extension.
        """
        if self._path.is_dir():
            for path in sorted(self._path.rglob("*.csv")):
                if path.is_file():
                    async for doc in self._stream_file(path):
                        yield doc
            return

        if not self._path.is_file():
            raise FileNotFoundError(f"File not found: {self._path}")
        if self._path.suffix.lower() != ".csv":
            raise ValueError(
                f"CSVLoader expects a .csv file, got {self._path.suffix!r}"
            )

        async for doc in self._stream_file(self._path):
            yield doc