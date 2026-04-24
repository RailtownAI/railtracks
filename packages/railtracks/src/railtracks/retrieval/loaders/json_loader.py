from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from railtracks.retrieval.loaders.base import BaseDocumentLoader
from railtracks.retrieval.models import Document, DocumentType


class JSONLoader(BaseDocumentLoader):
    """Loads JSON files, converting each object in an array into a Document.

    If `file_path` points to a directory, all `.json` files are loaded
    recursively. If it points to a file, that file is loaded.

    The file must contain either a JSON array of objects, or a single object.

    Args:
        file_path: Path to a `.json` file or directory.
        content_keys: Keys whose values are concatenated to form `Document.content`.
            When `None`, the entire object is serialized as content.
        ignore_keys: Keys to drop entirely — not content, not metadata.
        content_separator: String used to join multiple content-key values.
        encoding: File encoding (default `utf-8-sig`).
    """

    def __init__(
        self,
        file_path: str,
        content_keys: list[str] | None = None,
        ignore_keys: list[str] | None = None,
        content_separator: str = "\n",
        encoding: str = "utf-8-sig",
    ) -> None:
        self._path = Path(file_path)
        self._content_keys = content_keys
        self._ignore_keys = set(ignore_keys or [])
        self._content_separator = content_separator
        self._encoding = encoding

    def _object_to_document(self, obj: dict[str, Any], source: str, index: int) -> Document:
        if self._content_keys is not None:
            unknown = [k for k in self._content_keys if k not in obj]
            if unknown:
                raise ValueError(
                    f"content_keys {unknown} not found in object at index {index} in {source}"
                )
            content = self._content_separator.join(
                f"{k}: {obj[k]}" for k in self._content_keys
            )
            content_key_set = set(self._content_keys)
            metadata: dict[str, Any] = {
                k: v
                for k, v in obj.items()
                if k not in content_key_set and k not in self._ignore_keys
            }
        else:
            content = json.dumps(
                {k: v for k, v in obj.items() if k not in self._ignore_keys},
                ensure_ascii=False,
            )
            metadata = {}

        metadata["index"] = index
        return Document(content=content, type=DocumentType.JSON, source=source, metadata=metadata)

    def _load_file(self, path: Path) -> list[Document]:
        source = str(path)
        raw = json.loads(path.read_text(encoding=self._encoding))

        objects: list[dict[str, Any]] = [raw] if isinstance(raw, dict) else raw

        if not isinstance(objects, list) or not all(isinstance(o, dict) for o in objects):
            raise ValueError(
                f"JSON file must contain an object or an array of objects: {path}"
            )

        return [self._object_to_document(obj, source, i) for i, obj in enumerate(objects)]

    def load(self) -> list[Document]:
        if self._path.is_dir():
            docs: list[Document] = []
            for p in sorted(self._path.rglob("*.json")):
                if p.is_file():
                    docs.extend(self._load_file(p))
            return docs

        if not self._path.is_file():
            raise FileNotFoundError(f"File not found: {self._path}")
        if self._path.suffix.lower() != ".json":
            raise ValueError(
                f"JSONLoader expects a .json file, got {self._path.suffix!r}"
            )

        return self._load_file(self._path)