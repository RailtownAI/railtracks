"""Unit tests for S3Loader."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from railtracks.retrieval.models import Document, DocumentType

from .conftest import make_s3_client


# ---------------------------------------------------------------------------
# S3Loader
# ---------------------------------------------------------------------------


class TestS3LoaderInit:
    def test_raises_import_error_when_boto3_missing(self) -> None:
        with patch.dict(sys.modules, {"boto3": None}):
            from railtracks.retrieval.loaders.cloud.s3 import S3Loader

            with pytest.raises(ImportError, match="boto3"):
                S3Loader("bucket")

    def test_import_error_message_mentions_extra(self) -> None:
        with patch.dict(sys.modules, {"boto3": None}):
            from railtracks.retrieval.loaders.cloud.s3 import S3Loader

            with pytest.raises(ImportError, match="railtracks\\[aws\\]"):
                S3Loader("bucket")


class TestS3LoaderKeys:
    def test_returns_document_for_each_key(self) -> None:
        from railtracks.retrieval.loaders.cloud.s3 import S3Loader

        objects = {"doc1.txt": "hello world", "doc2.txt": "foo bar"}
        mock_client = make_s3_client(objects)

        with patch("boto3.client", return_value=mock_client):
            loader = S3Loader("my-bucket", keys=list(objects.keys()))

        docs = loader.load()

        assert len(docs) == 2
        assert all(isinstance(d, Document) for d in docs)

    def test_document_content_matches_object_body(self) -> None:
        from railtracks.retrieval.loaders.cloud.s3 import S3Loader

        mock_client = make_s3_client({"notes.txt": "some text content"})
        with patch("boto3.client", return_value=mock_client):
            loader = S3Loader("my-bucket", keys=["notes.txt"])

        (doc,) = loader.load()
        assert doc.content == "some text content"

    def test_document_source_is_full_uri(self) -> None:
        from railtracks.retrieval.loaders.cloud.s3 import S3Loader

        mock_client = make_s3_client({"path/to/file.txt": "data"})
        with patch("boto3.client", return_value=mock_client):
            loader = S3Loader("my-bucket", keys=["path/to/file.txt"])

        (doc,) = loader.load()
        assert doc.source == "s3://my-bucket/path/to/file.txt"

    def test_document_metadata_contains_bucket_and_key(self) -> None:
        from railtracks.retrieval.loaders.cloud.s3 import S3Loader

        mock_client = make_s3_client({"file.txt": "data"})
        with patch("boto3.client", return_value=mock_client):
            loader = S3Loader("my-bucket", keys=["file.txt"])

        (doc,) = loader.load()
        assert doc.metadata["bucket"] == "my-bucket"
        assert doc.metadata["key"] == "file.txt"

    def test_document_type_inferred_from_extension(self) -> None:
        from railtracks.retrieval.loaders.cloud.s3 import S3Loader

        mock_client = make_s3_client({"a.md": "x", "b.txt": "y", "c.json": "{}"})
        with patch("boto3.client", return_value=mock_client):
            loader = S3Loader("my-bucket", keys=["a.md", "b.txt", "c.json"])

        types = {d.source.split("/")[-1]: d.type for d in loader.load()}
        assert types["a.md"] == DocumentType.MARKDOWN
        assert types["b.txt"] == DocumentType.TEXT
        assert types["c.json"] == DocumentType.JSON

    def test_custom_encoding_is_used(self) -> None:
        from railtracks.retrieval.loaders.cloud.s3 import S3Loader

        text = "café"
        mock_client = make_s3_client({"file.txt": text}, encoding="latin-1")
        with patch("boto3.client", return_value=mock_client):
            loader = S3Loader("my-bucket", keys=["file.txt"], encoding="latin-1")

        (doc,) = loader.load()
        assert doc.content == text


class TestS3LoaderList:
    def test_load_without_prefix_returns_all_objects(self) -> None:
        from railtracks.retrieval.loaders.cloud.s3 import S3Loader

        objects = {"a.txt": "aaa", "b.txt": "bbb", "c.txt": "ccc"}
        mock_client = make_s3_client(objects)
        with patch("boto3.client", return_value=mock_client):
            loader = S3Loader("my-bucket")

        docs = loader.load()
        assert len(docs) == 3
        assert {d.content for d in docs} == {"aaa", "bbb", "ccc"}

    def test_prefix_passed_to_paginator(self) -> None:
        from railtracks.retrieval.loaders.cloud.s3 import S3Loader

        mock_client = make_s3_client({"docs/a.txt": "aaa"})
        with patch("boto3.client", return_value=mock_client):
            loader = S3Loader("my-bucket", prefix="docs/")

        loader.load()

        paginator = mock_client.get_paginator.return_value
        paginator.paginate.assert_called_once_with(Bucket="my-bucket", Prefix="docs/")

    def test_no_prefix_omits_prefix_kwarg(self) -> None:
        from railtracks.retrieval.loaders.cloud.s3 import S3Loader

        mock_client = make_s3_client({})
        with patch("boto3.client", return_value=mock_client):
            loader = S3Loader("my-bucket")

        loader.load()

        call_kwargs = mock_client.get_paginator.return_value.paginate.call_args.kwargs
        assert "Prefix" not in call_kwargs

    def test_empty_bucket_returns_empty_list(self) -> None:
        from railtracks.retrieval.loaders.cloud.s3 import S3Loader

        client = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [{}]
        client.get_paginator.return_value = paginator

        with patch("boto3.client", return_value=client):
            loader = S3Loader("empty-bucket")

        assert loader.load() == []

    def test_prefix_recurses_into_nested_keys(self) -> None:
        """Listing under a prefix returns all matching keys regardless of '/' depth."""
        from railtracks.retrieval.loaders.cloud.s3 import S3Loader

        objects = {
            "docs/top.txt": "t",
            "docs/A/B.txt": "n1",
            "docs/A/deep/C.txt": "n2",
        }
        mock_client = make_s3_client(objects)
        with patch("boto3.client", return_value=mock_client):
            loader = S3Loader("my-bucket", prefix="docs/")

        docs = loader.load()
        # Source preserves the full nested key path
        sources = sorted(d.source for d in docs)
        assert sources == [
            "s3://my-bucket/docs/A/B.txt",
            "s3://my-bucket/docs/A/deep/C.txt",
            "s3://my-bucket/docs/top.txt",
        ]
        # And metadata['key'] keeps the nested structure for downstream filtering
        keys = sorted(d.metadata["key"] for d in docs)
        assert keys == ["docs/A/B.txt", "docs/A/deep/C.txt", "docs/top.txt"]


@pytest.mark.asyncio
class TestS3LoaderAsync:
    async def test_aload_returns_documents(self) -> None:
        from railtracks.retrieval.loaders.cloud.s3 import S3Loader

        mock_client = make_s3_client({"file.txt": "hello"})
        with patch("boto3.client", return_value=mock_client):
            loader = S3Loader("my-bucket", keys=["file.txt"])

        async_ = await loader.aload()
        assert len(async_) == 1
        assert async_[0].content == "hello"

    async def test_astream_yields_documents(self) -> None:
        from railtracks.retrieval.loaders.cloud.s3 import S3Loader

        mock_client = make_s3_client({"a.txt": "x", "b.txt": "y"})
        with patch("boto3.client", return_value=mock_client):
            loader = S3Loader("my-bucket")

        docs = [doc async for doc in loader.astream()]
        assert len(docs) == 2
        assert all(isinstance(d, Document) for d in docs)
