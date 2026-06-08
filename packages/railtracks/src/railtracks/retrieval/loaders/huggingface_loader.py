from __future__ import annotations

import asyncio
import warnings
from collections.abc import AsyncGenerator, Iterator
from typing import Any, Final

from railtracks.retrieval.loaders.base import BaseDocumentLoader
from railtracks.retrieval.models import Document, DocumentType

try:
    from datasets import IterableDataset, IterableDatasetDict, load_dataset
except ImportError as exc:
    raise ImportError(
        "datasets is required for HuggingFaceDatasetLoader. "
        'Install it with: pip install "railtracks[huggingface]"'
    ) from exc


# asyncio.to_thread can't surface StopIteration across the thread boundary, so we use a sentinel default and stop when next() returns it.
class _Missing:
    pass


_SENTINEL: Final[_Missing] = _Missing()


class HuggingFaceDatasetLoader(BaseDocumentLoader):
    """Loads a Hugging Face dataset as Document objects.

    Each row of the chosen split becomes one Document. Rows are pulled from the Hub one at a time in streaming mode, so this works fine on datasets that wouldn't fit in memory (`wiki_dpr`, `c4`, etc.).

    Column handling:

    - `content_columns`: values are joined by `content_separator` to form
      `Document.content`. Required.
    - `metadata_columns`: copied into `Document.metadata` as-is.
    - `row_index` is added to metadata automatically (0-based position
      within the split).
    - `Document.source` is set to `"{dataset_name}/{split}#{row_id}"`,
      where `row_id` is `row[id_column]` when `id_column` is given and
      `row_index` otherwise. Per-row sources keep `Document.id` stable
      and unique across rows, which is what the runtime needs for
      upsert (`delete_where` on `document_id`).

    Args:
        dataset_name: Dataset name on the Hugging Face Hub
            (e.g. `"squad"`, `"ms_marco"`).
        split: Which split to stream (`"train"`, `"validation"`, etc.).
        content_columns: Columns whose values get joined into
            `Document.content`.
        id_column: Column whose value uniquely identifies a row (e.g.
            `"id"`, `"qid"`, `"_id"`). Used as the row id in
            `Document.source`. Default: None (fall back to `row_index`).
            Prefer this when the dataset exposes a stable id and may be
            re-shuffled upstream — `row_index` is only stable as long as
            the dataset order is.
        metadata_columns: Columns to copy into `Document.metadata`.
            Default : None.
        content_separator: Separator used to join `content_columns`
            values. Default: `"\\n"`.
        dataset_kwargs: Extra keyword arguments forwarded to
            `datasets.load_dataset`. Use this for subset selection
            (`{"name": "v2.1"}`), pinning a revision, or passing an
            auth token. `streaming=True` is always set; any `streaming`
            entry here is ignored.

    Raises:
        ValueError: If `content_columns` is empty, or if any name in
            `content_columns`, `metadata_columns`, or `id_column` isn't
            present in the dataset schema.
    """

    def __init__(
        self,
        dataset_name: str,
        split: str,
        content_columns: list[str],
        id_column: str | None = None,
        metadata_columns: list[str] | None = None,
        content_separator: str = "\n",
        dataset_kwargs: dict[str, Any] | None = None,
    ) -> None:
        if not content_columns:
            raise ValueError("content_columns must be a non-empty list of column names")
        self._dataset_name = dataset_name
        self._split = split
        self._content_columns = list(content_columns)
        self._id_column = id_column
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
            ValueError: If a column in `content_columns` or
                `metadata_columns` isn't present in the dataset schema.
        """
        kwargs = dict(self._dataset_kwargs)
        if kwargs.pop("streaming", None) is not None:
            warnings.warn(
                "`streaming` in dataset_kwargs is ignored; "
                "HuggingFaceDatasetLoader always streams.",
                stacklevel=2,
            )
        kwargs["split"] = self._split

        dataset: IterableDataset | IterableDatasetDict = await asyncio.to_thread(
            load_dataset, self._dataset_name, streaming=True, **kwargs
        )
        if isinstance(dataset, IterableDatasetDict):
            if self._split not in dataset:
                raise ValueError(
                    f"Split {self._split!r} not found in dataset {self._dataset_name!r}"
                )
            dataset = dataset[self._split]

        iterator: Iterator[dict[str, Any]] = iter(dataset)
        source_prefix = f"{self._dataset_name}/{self._split}"
        validated = False
        row_index = 0

        while True:
            row = await asyncio.to_thread(next, iterator, _SENTINEL)
            if isinstance(row, _Missing):
                return

            if not validated:
                missing_content = [c for c in self._content_columns if c not in row]
                missing_metadata = [c for c in self._metadata_columns if c not in row]
                if missing_content:
                    raise ValueError(
                        f"content_columns not found in dataset schema: {missing_content}"
                    )
                if missing_metadata:
                    raise ValueError(
                        f"metadata_columns not found in dataset schema: {missing_metadata}"
                    )
                if self._id_column is not None and self._id_column not in row:
                    raise ValueError(
                        f"id_column not found in dataset schema: {self._id_column!r}"
                    )
                validated = True

            content = self._content_separator.join(
                str(row[col]) for col in self._content_columns
            )
            metadata: dict[str, Any] = {col: row[col] for col in self._metadata_columns}
            metadata["row_index"] = row_index

            row_id = (
                str(row[self._id_column])
                if self._id_column is not None
                else str(row_index)
            )

            yield Document(
                content=content,
                type=DocumentType.TEXT,
                source=f"{source_prefix}#{row_id}",
                metadata=metadata,
            )
            row_index += 1
