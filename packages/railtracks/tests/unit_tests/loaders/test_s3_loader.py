import sys
from unittest.mock import patch

import pytest

from railtracks.loaders.s3 import S3Loader
from railtracks.vector_stores.chunking.base_chunker import Chunk

from .conftest import make_s3_client


class TestS3LoaderInit:
    def test_raises_import_error_when_boto3_missing(self) -> None:
        with patch.dict(sys.modules, {"boto3": None}):
            with pytest.raises(ImportError, match="boto3"):
                S3Loader("bucket")

    def test_import_error_message_mentions_extra(self) -> None:
        with patch.dict(sys.modules, {"boto3": None}):
            with pytest.raises(ImportError, match="railtracks\\[aws\\]"):
                S3Loader("bucket")


class TestS3LoaderLoadKeys:
    def test_returns_chunk_for_each_key(self) -> None:
        objects = {"doc1.txt": "hello world", "doc2.txt": "foo bar"}
        mock_client = make_s3_client(objects)

        with patch("boto3.client", return_value=mock_client):
            loader = S3Loader("my-bucket")

        chunks = loader.load_keys(list(objects.keys()))

        assert len(chunks) == 2
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_chunk_content_matches_object_body(self) -> None:
        mock_client = make_s3_client({"notes.txt": "some text content"})

        with patch("boto3.client", return_value=mock_client):
            loader = S3Loader("my-bucket")

        (chunk,) = loader.load_keys(["notes.txt"])
        assert chunk.content == "some text content"

    def test_chunk_document_is_object_key(self) -> None:
        mock_client = make_s3_client({"path/to/file.txt": "data"})

        with patch("boto3.client", return_value=mock_client):
            loader = S3Loader("my-bucket")

        (chunk,) = loader.load_keys(["path/to/file.txt"])
        assert chunk.document == "path/to/file.txt"

    def test_chunk_metadata_contains_source_url(self) -> None:
        mock_client = make_s3_client({"file.txt": "data"})

        with patch("boto3.client", return_value=mock_client):
            loader = S3Loader("my-bucket")

        (chunk,) = loader.load_keys(["file.txt"])
        assert chunk.metadata["source"] == "s3://my-bucket/file.txt"
        assert chunk.metadata["bucket"] == "my-bucket"
        assert chunk.metadata["key"] == "file.txt"

    def test_custom_encoding_is_used(self) -> None:
        text = "café"
        mock_client = make_s3_client({"file.txt": text}, encoding="latin-1")

        with patch("boto3.client", return_value=mock_client):
            loader = S3Loader("my-bucket", encoding="latin-1")

        (chunk,) = loader.load_keys(["file.txt"])
        assert chunk.content == text

    def test_empty_keys_returns_empty_list(self) -> None:
        mock_client = make_s3_client({})

        with patch("boto3.client", return_value=mock_client):
            loader = S3Loader("my-bucket")

        assert loader.load_keys([]) == []


class TestS3LoaderLoad:
    def test_load_without_prefix_returns_all_objects(self) -> None:
        objects = {"a.txt": "aaa", "b.txt": "bbb", "c.txt": "ccc"}
        mock_client = make_s3_client(objects)

        with patch("boto3.client", return_value=mock_client):
            loader = S3Loader("my-bucket")

        chunks = loader.load()

        assert len(chunks) == 3
        assert {c.content for c in chunks} == {"aaa", "bbb", "ccc"}

    def test_load_passes_prefix_to_paginator(self) -> None:
        mock_client = make_s3_client({"docs/a.txt": "aaa", "docs/b.txt": "bbb"})

        with patch("boto3.client", return_value=mock_client):
            loader = S3Loader("my-bucket")

        loader.load(prefix="docs/")

        paginator = mock_client.get_paginator.return_value
        paginator.paginate.assert_called_once_with(Bucket="my-bucket", Prefix="docs/")

    def test_load_without_prefix_omits_prefix_kwarg(self) -> None:
        mock_client = make_s3_client({})

        with patch("boto3.client", return_value=mock_client):
            loader = S3Loader("my-bucket")

        loader.load()

        call_kwargs = mock_client.get_paginator.return_value.paginate.call_args.kwargs
        assert "Prefix" not in call_kwargs

    def test_empty_bucket_returns_empty_list(self) -> None:
        from unittest.mock import MagicMock

        client = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [{}]  # no "Contents" key
        client.get_paginator.return_value = paginator

        with patch("boto3.client", return_value=client):
            loader = S3Loader("empty-bucket")

        assert loader.load() == []


@pytest.mark.asyncio
class TestS3LoaderAsync:
    async def test_aload_returns_same_chunks_as_load(self) -> None:
        mock_client = make_s3_client({"file.txt": "hello"})

        with patch("boto3.client", return_value=mock_client):
            loader = S3Loader("my-bucket")

        sync_chunks = loader.load()
        async_chunks = await loader.aload()

        assert len(async_chunks) == len(sync_chunks)
        assert async_chunks[0].content == sync_chunks[0].content

    async def test_aload_keys_returns_same_chunks_as_load_keys(self) -> None:
        mock_client = make_s3_client({"file.txt": "hello"})

        with patch("boto3.client", return_value=mock_client):
            loader = S3Loader("my-bucket")

        sync_chunks = loader.load_keys(["file.txt"])
        async_chunks = await loader.aload_keys(["file.txt"])

        assert len(async_chunks) == len(sync_chunks)
        assert async_chunks[0].content == sync_chunks[0].content
