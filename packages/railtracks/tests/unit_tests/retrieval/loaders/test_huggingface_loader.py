from __future__ import annotations

from unittest.mock import patch

import pytest
from railtracks.retrieval.loaders.huggingface_loader import (
    HuggingFaceDatasetLoader,
)
from railtracks.retrieval.models import DocumentType


class _FakeIterableDataset:
    """Stand-in for ``datasets.IterableDataset``.

    HF streaming datasets are iterable and produce one ``dict`` per row.
    Tracking ``consumed`` lets us prove the loader pulls rows lazily.
    """

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self.consumed: list[dict] = []

    def __iter__(self):
        for row in self._rows:
            self.consumed.append(row)
            yield row


@pytest.fixture
def fake_rows() -> list[dict]:
    return [
        {"query": "what is rag", "passage": "Retrieval-augmented generation.", "label": 1, "topic": "ml"},
        {"query": "what is bm25", "passage": "BM25 is a ranking function.", "label": 0, "topic": "ir"},
        {"query": "what is dpr", "passage": "Dense passage retrieval.", "label": 1, "topic": "ir"},
    ]


@pytest.fixture
def fake_dataset(fake_rows):
    return _FakeIterableDataset(fake_rows)


@pytest.fixture
def mock_load_dataset(fake_dataset):
    with patch(
        "railtracks.retrieval.loaders.huggingface_loader.load_dataset",
        return_value=fake_dataset,
    ) as m:
        yield m


class TestHuggingFaceLoaderBasic:
    """Core happy-path behaviour."""

    async def test_yields_one_document_per_row(self, mock_load_dataset, fake_rows):
        docs = await HuggingFaceDatasetLoader(
            "fake/ds", split="train", content_columns=["query"]
        ).aload()
        assert len(docs) == len(fake_rows)

    async def test_document_type_is_text(self, mock_load_dataset):
        docs = await HuggingFaceDatasetLoader(
            "fake/ds", split="train", content_columns=["query"]
        ).aload()
        assert all(d.type == DocumentType.TEXT for d in docs)

    async def test_source_is_dataset_name_and_split(self, mock_load_dataset):
        docs = await HuggingFaceDatasetLoader(
            "fake/ds", split="validation", content_columns=["query"]
        ).aload()
        assert all(d.source == "fake/ds/validation" for d in docs)

    async def test_row_index_in_metadata(self, mock_load_dataset, fake_rows):
        docs = await HuggingFaceDatasetLoader(
            "fake/ds", split="train", content_columns=["query"]
        ).aload()
        assert [d.metadata["row_index"] for d in docs] == list(range(len(fake_rows)))


class TestHuggingFaceLoaderContentColumns:
    """``content_columns`` joining + separator behaviour."""

    async def test_single_content_column(self, mock_load_dataset):
        docs = await HuggingFaceDatasetLoader(
            "fake/ds", split="train", content_columns=["query"]
        ).aload()
        assert docs[0].content == "what is rag"

    async def test_multiple_content_columns_joined_with_separator(
        self, mock_load_dataset
    ):
        docs = await HuggingFaceDatasetLoader(
            "fake/ds",
            split="train",
            content_columns=["query", "passage"],
            content_separator=" | ",
        ).aload()
        assert docs[0].content == "what is rag | Retrieval-augmented generation."

    async def test_non_string_values_are_stringified(self, mock_load_dataset):
        docs = await HuggingFaceDatasetLoader(
            "fake/ds", split="train", content_columns=["label"]
        ).aload()
        assert docs[0].content == "1"


class TestHuggingFaceLoaderMetadataColumns:
    """``metadata_columns`` forwarding."""

    async def test_metadata_columns_forwarded(self, mock_load_dataset):
        docs = await HuggingFaceDatasetLoader(
            "fake/ds",
            split="train",
            content_columns=["query"],
            metadata_columns=["label", "topic"],
        ).aload()
        assert docs[0].metadata["label"] == 1
        assert docs[0].metadata["topic"] == "ml"

    async def test_metadata_columns_default_to_only_row_index(
        self, mock_load_dataset
    ):
        docs = await HuggingFaceDatasetLoader(
            "fake/ds", split="train", content_columns=["query"]
        ).aload()
        assert set(docs[0].metadata.keys()) == {"row_index"}


class TestHuggingFaceLoaderValidation:
    """Schema-validation and constructor guards."""

    def test_empty_content_columns_raises_in_constructor(self):
        with pytest.raises(ValueError, match="content_columns must be a non-empty"):
            HuggingFaceDatasetLoader("fake/ds", split="train", content_columns=[])

    async def test_unknown_content_column_raises_value_error(
        self, mock_load_dataset
    ):
        loader = HuggingFaceDatasetLoader(
            "fake/ds", split="train", content_columns=["does_not_exist"]
        )
        with pytest.raises(
            ValueError, match="content_columns not found in dataset schema"
        ):
            await loader.aload()

    async def test_unknown_metadata_column_raises_value_error(
        self, mock_load_dataset
    ):
        loader = HuggingFaceDatasetLoader(
            "fake/ds",
            split="train",
            content_columns=["query"],
            metadata_columns=["does_not_exist"],
        )
        with pytest.raises(
            ValueError, match="metadata_columns not found in dataset schema"
        ):
            await loader.aload()


class TestHuggingFaceLoaderStreaming:
    """Laziness guarantees and ``load_dataset`` call shape."""

    async def test_astream_pulls_one_row_at_a_time(
        self, mock_load_dataset, fake_dataset
    ):
        loader = HuggingFaceDatasetLoader(
            "fake/ds", split="train", content_columns=["query"]
        )
        gen = loader.astream()
        try:
            await gen.__anext__()
            assert len(fake_dataset.consumed) == 1
            await gen.__anext__()
            assert len(fake_dataset.consumed) == 2
        finally:
            await gen.aclose()

    async def test_streaming_enabled_by_default(self, mock_load_dataset):
        await HuggingFaceDatasetLoader(
            "fake/ds", split="train", content_columns=["query"]
        ).aload()
        _, kwargs = mock_load_dataset.call_args
        assert kwargs["streaming"] is True
        assert kwargs["split"] == "train"

    async def test_dataset_kwargs_forwarded(self, mock_load_dataset):
        await HuggingFaceDatasetLoader(
            "fake/ds",
            split="train",
            content_columns=["query"],
            dataset_kwargs={"name": "v2.1", "revision": "abc"},
        ).aload()
        _, kwargs = mock_load_dataset.call_args
        assert kwargs["name"] == "v2.1"
        assert kwargs["revision"] == "abc"

    async def test_dataset_kwargs_can_override_streaming(self, mock_load_dataset):
        await HuggingFaceDatasetLoader(
            "fake/ds",
            split="train",
            content_columns=["query"],
            dataset_kwargs={"streaming": False},
        ).aload()
        _, kwargs = mock_load_dataset.call_args
        assert kwargs["streaming"] is False


class TestHuggingFaceLoaderSyncWrapper:
    """``.load()`` blocking wrapper inherited from ``BaseDocumentLoader``."""

    def test_load_returns_same_documents_as_aload(self, mock_load_dataset, fake_rows):
        docs = HuggingFaceDatasetLoader(
            "fake/ds", split="train", content_columns=["query"]
        ).load()
        assert len(docs) == len(fake_rows)
        assert docs[0].metadata["row_index"] == 0
