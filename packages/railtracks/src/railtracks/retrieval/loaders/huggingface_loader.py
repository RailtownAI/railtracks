from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

from railtracks.retrieval.loaders.base import BaseDocumentLoader
from railtracks.retrieval.models import Document, DocumentType

try:
    from datasets import load_dataset
except ImportError as exc:
    raise ImportError(
        "datasets is required for HuggingFaceDatasetLoader. "
        'Install it with: pip install "railtracks[huggingface]"'
    ) from exc


# asyncio.to_thread can't surface StopIteration across the thread boundary, so we use a sentinel default and stop when next() returns it.
_SENTINEL: object = object()


class HuggingFaceDatasetLoader(BaseDocumentLoader):
    """Loads a Hugging Face dataset as Document objects.

    Each row of the chosen split becomes one Document. Rows are pulled from the Hub one at a time in streaming mode, so this works fine on datasets that wouldn't fit in memory (`wiki_dpr`, `c4`, etc.).

    Column handling:

    - `content_columns`: values are joined by `content_separator` to form
      `Document.content`. Required.
    - `metadata_columns`: copied into `Document.metadata` as-is.
    - `row_index` is added to metadata automatically (0-based position
      within the split).
    - `Document.source` is set to `"{dataset_name}/{split}"`.

    Args:
        dataset_name: Dataset name on the Hugging Face Hub
            (e.g. `"squad"`, `"ms_marco"`).
        split: Which split to stream (`"train"`, `"validation"`, etc.).
        content_columns: Columns whose values get joined into
            `Document.content`.
        metadata_columns: Columns to copy into `Document.metadata`.
            Default : None.
        content_separator: Separator used to join `content_columns`
            values. Default: `"\\n"`.
        dataset_kwargs: Extra keyword arguments forwarded to
            `datasets.load_dataset`. Use this for subset selection
            (`{"name": "v2.1"}`), pinning a revision, or passing an
            auth token. `streaming=True` is set by default and can be
            overridden here.

    Raises:
        ValueError: If `content_columns` is empty, or if any name in
            `content_columns` isn't present in the dataset schema.
    """

    def __init__(
        self,
        dataset_name: str,
        split: str,
        content_columns: list[str],
        metadata_columns: list[str] | None = None,
        content_separator: str = "\n",
        dataset_kwargs: dict[str, Any] | None = None,
    ) -> None:
        if not content_columns:
            raise ValueError("content_columns must be a non-empty list of column names")
        self._dataset_name = dataset_name
        self._split = split
        self._content_columns = list(content_columns)
        self._metadata_columns = list(metadata_columns or [])
        self._content_separator = content_separator
        self._dataset_kwargs = dict(dataset_kwargs or {})

    async def astream(self) -> AsyncGenerator[Document, None]:
        """Yield one `Document` per row, pulled lazily from the Hub.

        Schema validation runs on the first row instead of upfront — some
        streaming datasets don't expose their `features` ahead of time, so
        peeking at the first row is the only reliable check.

        Yields:
            Document: The next row as a document.

        Raises:
            ValueError: If a column in `content_columns` isn't present in
                the dataset schema.
        """
        kwargs = dict(self._dataset_kwargs)
        kwargs.setdefault("streaming", True)
        kwargs["split"] = self._split

        dataset = await asyncio.to_thread(load_dataset, self._dataset_name, **kwargs)

        iterator = iter(dataset)
        source = f"{self._dataset_name}/{self._split}"
        validated = False
        row_index = 0

        while True:
            row = await asyncio.to_thread(next, iterator, _SENTINEL)
            if row is _SENTINEL:
                return

            if not validated:
                missing = [c for c in self._content_columns if c not in row]
                if missing:
                    raise ValueError(
                        f"content_columns not found in dataset schema: {missing}"
                    )
                validated = True

            content = self._content_separator.join(
                str(row[col]) for col in self._content_columns
            )
            metadata: dict[str, Any] = {
                col: row[col] for col in self._metadata_columns if col in row
            }
            metadata["row_index"] = row_index

            yield Document(
                content=content,
                type=DocumentType.TEXT,
                source=source,
                metadata=metadata,
            )
            row_index += 1
