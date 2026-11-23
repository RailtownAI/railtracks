from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from railtracks.retrieval.content_extraction import (
    ContentExtractor,
    JsonExtractor,
    labelled_join,
)
from railtracks.retrieval.loaders.base import (
    RENAMED_ARGUMENTS_GUIDE,
    BaseDocumentLoader,
)
from railtracks.retrieval.loaders.models import LoadFailure
from railtracks.retrieval.models import Document, DocumentType
from railtracks.utils.deprecation import renamed_kwargs


class JSONLoader(BaseDocumentLoader):
    """Loads JSON and JSON Lines files as `Document` objects.

    If `file_path` points to a directory, all `.json` and `.jsonl` files are
    loaded recursively in sorted order. If it points to a file, that file is
    loaded; the format is selected by suffix.

    - `.json`: the file root must be a JSON object or an array of objects.
      For arrays, each element becomes a separate `Document`; for a single
      object, one `Document` is produced.
    - `.jsonl`: each non-empty line must be a JSON object; one `Document` per
      object. Blank lines are skipped. The file is streamed line by line, so
      JSONL is the preferred format for corpora larger than memory.

    `Document.source` is set to `"{file_path}#{obj_id}"`, where `obj_id`
    is `obj[id_column]` when `id_column` is given and the object's position
    in the file otherwise. Per-object sources keep `Document.id` stable and
    unique across objects, which is what the runtime needs for upsert
    (`delete_where` on `document_id`).

    Args:
        file_path: Path to a `.json` / `.jsonl` file, or a directory
            containing them.
        content_columns: Keys whose values form `Document.content`. Use
            `"*"` (default) to serialise the entire object as content. A
            single key name gives that key's value as-is; a list gives
            `"key: value"` lines joined with `content_separator`. All
            remaining non-ignored fields are added to `Document.metadata`.
        id_column: Top-level key whose value uniquely identifies an object
            (e.g. `"id"`, `"_id"`). Used as the object id in
            `Document.source`. Default: `None` (fall back to the object's
            position in the file). Prefer this when the JSON has a stable
            id field and objects may be reordered — position is only
            stable as long as the order is.
        ignore_columns: Keys to drop entirely from both content and metadata.
        content_separator: String used to join multiple content values.
            Defaults to `"\\n"`.
        encoding: File encoding. Defaults to `utf-8-sig`.
        content_extractor: Optional callable used to turn content values
            into text. When omitted, the loader preserves its existing JSON
            serialization for `content_columns="*"` and `str(value)` behavior
            for explicit keys.

    Raises:
        FileNotFoundError: If `file_path` does not exist.
        TypeError: If `content_keys`, `id_key` or `ignore_keys`, the
            deprecated names for `content_columns`, `id_column` and
            `ignore_columns` (removed in 2.0.0), is passed together with its
            replacement.
        ValueError: If `file_path` points to a file with an unsupported
            extension, the JSON/JSONL structure does not match the format
            (e.g. a `.json` file that is neither object nor array of
            objects, or a `.jsonl` line that is not a JSON object), or any
            key in `content_columns` or `id_column` is not found in a parsed
            object, or a content extractor fails (with key, index, and source).
    """

    @renamed_kwargs(
        content_keys="content_columns",
        id_key="id_column",
        ignore_keys="ignore_columns",
        version="2.0.0",
        guide=RENAMED_ARGUMENTS_GUIDE,
    )
    def __init__(
        self,
        file_path: str,
        content_columns: str | list[str] = "*",
        id_column: str | None = None,
        ignore_columns: list[str] | None = None,
        content_separator: str = "\n",
        encoding: str = "utf-8-sig",
        content_extractor: ContentExtractor | None = None,
    ) -> None:
        self._path = Path(file_path)
        self._all_content = content_columns == "*"
        self._single_column = isinstance(content_columns, str)
        self._content_columns = (
            [content_columns]
            if isinstance(content_columns, str)
            else list(content_columns)
        )
        self._id_column = id_column
        self._ignore_columns = set(ignore_columns or [])
        self._content_separator = content_separator
        # Unlike the HF loader, the default depends on the content-columns mode.
        self._content_extractor = content_extractor
        self._encoding = encoding

    def _object_to_document(
        self,
        obj: dict[str, Any],
        source_prefix: str,
        index: int,
        doc_type: DocumentType = DocumentType.JSON,
    ) -> Document:
        """Convert a single JSON object to a `Document`.

        Args:
            obj: The parsed JSON object.
            source_prefix: The source file path; the returned `Document.source`
                appends a per-object id suffix.
            index: The zero-based position of this object in the source file,
                added to `Document.metadata`.

        Returns:
            Document: The converted document.

        Raises:
            ValueError: If any key in `content_columns` or `id_column` is not
                present in `obj`.
        """
        if self._all_content:
            content_value = {
                k: v for k, v in obj.items() if k not in self._ignore_columns
            }
            content = self._extract_content(
                content_value, JsonExtractor(), "*", source_prefix, index
            )
            metadata: dict[str, Any] = {}
        else:
            unknown = [k for k in self._content_columns if k not in obj]
            if unknown:
                raise ValueError(
                    f"content_columns {unknown} not found in object at index {index} in {source_prefix}"
                )
            texts = [
                (k, self._extract_content(obj[k], str, k, source_prefix, index))
                for k in self._content_columns
            ]
            if self._single_column:
                content = texts[0][1]
            else:
                content = labelled_join(texts, self._content_separator)
            content_column_set = set(self._content_columns)
            metadata = {
                k: v
                for k, v in obj.items()
                if k not in content_column_set and k not in self._ignore_columns
            }

        if self._id_column is not None and self._id_column not in obj:
            raise ValueError(
                f"id_column {self._id_column!r} not found in object at index {index} in {source_prefix}"
            )
        obj_id = (
            str(obj[self._id_column]) if self._id_column is not None else str(index)
        )

        metadata["index"] = index
        return Document(
            content=content,
            type=doc_type,
            source=f"{source_prefix}#{obj_id}",
            metadata=metadata,
        )

    def _extract_content(
        self,
        value: Any,
        fallback: ContentExtractor,
        key: str,
        source_prefix: str,
        index: int,
    ) -> str:
        extractor = (
            self._content_extractor if self._content_extractor is not None else fallback
        )
        try:
            return extractor(value)
        except Exception as exc:
            raise ValueError(
                f"Content extraction failed for key {key!r} at index {index} in {source_prefix}: {exc!r}"
            ) from exc

    async def _stream_file(self, path: Path) -> AsyncGenerator[Document, None]:
        """Stream documents from a single JSON or JSONL file.

        Dispatches by suffix: `.jsonl` is streamed line by line; `.json`
        is parsed whole. One `Document` per object is yielded.

        Args:
            path: Path to the JSON or JSONL file to read.

        Yields:
            Document: The next converted document.

        Raises:
            ValueError: If a `.json` file does not contain an object or
                array of objects, or a `.jsonl` line is not a JSON object.
        """
        if path.suffix.lower() == ".jsonl":
            async for doc in self._stream_jsonl(path):
                yield doc
            return

        source_prefix = str(path)
        raw = await asyncio.to_thread(
            lambda: json.loads(path.read_text(encoding=self._encoding))
        )

        objects: list[dict[str, Any]] = [raw] if isinstance(raw, dict) else raw

        if not isinstance(objects, list) or not all(
            isinstance(o, dict) for o in objects
        ):
            raise ValueError(
                f"JSON file must contain an object or an array of objects: {path}"
            )

        for i, obj in enumerate(objects):
            yield self._object_to_document(obj, source_prefix, i)

    async def _stream_jsonl(self, path: Path) -> AsyncGenerator[Document, None]:
        """Stream documents from a single JSONL file, one object per line.

        Reads and parses the file line by line in a worker thread so the
        event loop is not blocked and the full file is never held in
        memory. Blank lines are skipped; the `index` exposed in
        `Document.metadata` counts only parsed objects, not raw lines.

        Args:
            path: Path to the JSONL file to read.

        Yields:
            Document: The next converted document.

        Raises:
            ValueError: If any non-empty line is not a JSON object.
        """
        source_prefix = str(path)
        f = await asyncio.to_thread(lambda: path.open(encoding=self._encoding))
        try:
            index = 0
            line_no = 0
            while True:
                raw_line = await asyncio.to_thread(f.readline)
                if not raw_line:
                    break
                line_no += 1
                stripped = raw_line.strip()
                if not stripped:
                    continue
                obj = json.loads(stripped)
                if not isinstance(obj, dict):
                    raise ValueError(
                        f"JSONL line must be a JSON object: line {line_no} in {path}"
                    )
                yield self._object_to_document(
                    obj, source_prefix, index, DocumentType.JSONL
                )
                index += 1
        finally:
            await asyncio.to_thread(f.close)

    async def astream(self) -> AsyncGenerator[Document | LoadFailure, None]:
        """Stream documents one at a time as each JSON object is parsed.

        Parses one file at a time, yielding each object as a `Document`
        immediately after parsing. For a directory, files are streamed in
        sorted order.

        Yields:
            Document | LoadFailure: The next converted document, or a
            `LoadFailure` for a file that could not be read.

        Raises:
            FileNotFoundError: If the path does not exist.
            ValueError: If the path points to a file with an unsupported
                extension.
        """
        if self._path.is_dir():
            paths = sorted(
                p
                for pattern in ("*.json", "*.jsonl")
                for p in self._path.rglob(pattern)
                if p.is_file()
            )
            for path in paths:
                async for item in self._isolate_source(
                    str(path), self._stream_file(path)
                ):
                    yield item
            return

        if not self._path.is_file():
            raise FileNotFoundError(f"File not found: {self._path}")
        if self._path.suffix.lower() not in (".json", ".jsonl"):
            raise ValueError(
                f"JSONLoader expects a .json or .jsonl file, got {self._path.suffix!r}"
            )

        async for item in self._isolate_source(
            str(self._path), self._stream_file(self._path)
        ):
            yield item
