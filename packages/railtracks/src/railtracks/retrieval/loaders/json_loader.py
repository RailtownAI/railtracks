from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, Literal

from railtracks.retrieval.loaders.base import BaseDocumentLoader
from railtracks.retrieval.models import Document, DocumentType


class JSONLoader(BaseDocumentLoader):
    """Loads JSON files as `Document` objects.

    If `file_path` points to a directory, all `.json` files are loaded
    recursively in sorted order. If it points to a file, that file is loaded.

    Each file must contain either a JSON object or a JSON array of objects.
    For arrays, each element becomes a separate `Document`. For a single
    object, one `Document` is produced.

    `Document.source` is set to `"{file_path}#{obj_id}"`, where `obj_id`
    is `obj[id_key]` when `id_key` is given and the object's position in
    the file otherwise. Per-object sources keep `Document.id` stable and
    unique across objects, which is what the runtime needs for upsert
    (`delete_where` on `document_id`).

    Args:
        file_path: Path to a `.json` file or a directory containing `.json`
            files.
        content_keys: Keys whose values are concatenated to form
            `Document.content`. Use `"*"` (default) to serialise the entire
            object as content. Pass an explicit list to control which fields
            become content — all remaining non-ignored fields are added to
            `Document.metadata`.
        id_key: Top-level key whose value uniquely identifies an object
            (e.g. `"id"`, `"_id"`). Used as the object id in
            `Document.source`. Default: `None` (fall back to the object's
            position in the file). Prefer this when the JSON has a stable
            id field and objects may be reordered — position is only
            stable as long as the array order is.
        ignore_keys: Keys to drop entirely from both content and metadata.
        content_separator: String used to join multiple content-key values.
            Defaults to `"\\n"`.
        encoding: File encoding. Defaults to `utf-8-sig`.

    Raises:
        FileNotFoundError: If `file_path` does not exist.
        ValueError: If `file_path` points to a file with an unsupported
            extension, the JSON structure is not an object or array of
            objects, or any key in `content_keys` or `id_key` is not
            found in a parsed object.
    """

    def __init__(
        self,
        file_path: str,
        content_keys: list[str] | Literal["*"] = "*",
        id_key: str | None = None,
        ignore_keys: list[str] | None = None,
        content_separator: str = "\n",
        encoding: str = "utf-8-sig",
    ) -> None:
        self._path = Path(file_path)
        self._content_keys = content_keys
        self._id_key = id_key
        self._ignore_keys = set(ignore_keys or [])
        self._content_separator = content_separator
        self._encoding = encoding

    def _object_to_document(
        self, obj: dict[str, Any], source_prefix: str, index: int
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
            ValueError: If any key in `content_keys` or `id_key` is not
                present in `obj`.
        """
        if self._content_keys == "*":
            content = json.dumps(
                {k: v for k, v in obj.items() if k not in self._ignore_keys},
                ensure_ascii=False,
            )
            metadata: dict[str, Any] = {}
        else:
            unknown = [k for k in self._content_keys if k not in obj]
            if unknown:
                raise ValueError(
                    f"content_keys {unknown} not found in object at index {index} in {source_prefix}"
                )
            content = self._content_separator.join(
                f"{k}: {obj[k]}" for k in self._content_keys
            )
            content_key_set = set(self._content_keys)
            metadata = {
                k: v
                for k, v in obj.items()
                if k not in content_key_set and k not in self._ignore_keys
            }

        if self._id_key is not None and self._id_key not in obj:
            raise ValueError(
                f"id_key {self._id_key!r} not found in object at index {index} in {source_prefix}"
            )
        obj_id = str(obj[self._id_key]) if self._id_key is not None else str(index)

        metadata["index"] = index
        return Document(
            content=content,
            type=DocumentType.JSON,
            source=f"{source_prefix}#{obj_id}",
            metadata=metadata,
        )

    async def _stream_file(self, path: Path) -> AsyncGenerator[Document, None]:
        """Stream documents from a single JSON file.

        Parses the file in a thread, then yields one `Document` per object.

        Args:
            path: Path to the JSON file to read.

        Yields:
            Document: The next converted document.

        Raises:
            ValueError: If the file does not contain an object or array of
                objects.
        """
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

    async def astream(self) -> AsyncGenerator[Document, None]:
        """Stream documents one at a time as each JSON object is parsed.

        Parses one file at a time, yielding each object as a `Document`
        immediately after parsing. For a directory, files are streamed in
        sorted order.

        Yields:
            Document: The next converted document.

        Raises:
            FileNotFoundError: If the path does not exist.
            ValueError: If the path points to a file with an unsupported
                extension.
        """
        if self._path.is_dir():
            for path in sorted(self._path.rglob("*.json")):
                if path.is_file():
                    async for doc in self._stream_file(path):
                        yield doc
            return

        if not self._path.is_file():
            raise FileNotFoundError(f"File not found: {self._path}")
        if self._path.suffix.lower() != ".json":
            raise ValueError(
                f"JSONLoader expects a .json file, got {self._path.suffix!r}"
            )

        async for doc in self._stream_file(self._path):
            yield doc
