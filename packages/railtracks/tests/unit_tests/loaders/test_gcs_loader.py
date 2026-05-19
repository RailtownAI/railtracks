import sys
from unittest.mock import patch

import pytest

from railtracks.loaders.gcs import GCSLoader
from railtracks.vector_stores.chunking.base_chunker import Chunk

from .conftest import make_gcs_client, patch_gcs

BUCKET = "my-gcs-bucket"


class TestGCSLoaderInit:
    def test_raises_import_error_when_package_missing(self) -> None:
        with patch.dict(sys.modules, {"google.cloud.storage": None, "google.cloud": None}):
            with pytest.raises(ImportError, match="google-cloud-storage"):
                GCSLoader(BUCKET)

    def test_import_error_message_mentions_extra(self) -> None:
        with patch.dict(sys.modules, {"google.cloud.storage": None, "google.cloud": None}):
            with pytest.raises(ImportError, match="railtracks\\[gcp\\]"):
                GCSLoader(BUCKET)

    def test_explicit_credentials_forwarded_to_client(self) -> None:
        from unittest.mock import MagicMock

        fake_creds = MagicMock()
        gcs_client = make_gcs_client({})

        with patch_gcs(gcs_client) as mock_storage:
            GCSLoader(BUCKET, credentials=fake_creds)
            mock_storage.Client.assert_called_once_with(
                project=None, credentials=fake_creds
            )

    def test_project_forwarded_to_client(self) -> None:
        gcs_client = make_gcs_client({})

        with patch_gcs(gcs_client) as mock_storage:
            GCSLoader(BUCKET, project="my-project")
            mock_storage.Client.assert_called_once_with(
                project="my-project", credentials=None
            )


class TestGCSLoaderLoadKeys:
    def test_returns_chunk_for_each_key(self) -> None:
        objects = {"doc1.txt": "hello", "doc2.txt": "world"}
        gcs_client = make_gcs_client(objects)

        with patch_gcs(gcs_client):
            loader = GCSLoader(BUCKET)

        chunks = loader.load_keys(list(objects.keys()))

        assert len(chunks) == 2
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_chunk_content_matches_object_body(self) -> None:
        gcs_client = make_gcs_client({"notes.txt": "some text content"})

        with patch_gcs(gcs_client):
            loader = GCSLoader(BUCKET)

        (chunk,) = loader.load_keys(["notes.txt"])
        assert chunk.content == "some text content"

    def test_chunk_document_is_object_name(self) -> None:
        gcs_client = make_gcs_client({"path/to/file.txt": "data"})

        with patch_gcs(gcs_client):
            loader = GCSLoader(BUCKET)

        (chunk,) = loader.load_keys(["path/to/file.txt"])
        assert chunk.document == "path/to/file.txt"

    def test_chunk_metadata_source_url(self) -> None:
        gcs_client = make_gcs_client({"file.txt": "data"})

        with patch_gcs(gcs_client):
            loader = GCSLoader(BUCKET)

        (chunk,) = loader.load_keys(["file.txt"])
        assert chunk.metadata["source"] == f"gs://{BUCKET}/file.txt"
        assert chunk.metadata["bucket"] == BUCKET
        assert chunk.metadata["name"] == "file.txt"

    def test_custom_encoding_is_used(self) -> None:
        text = "café"
        gcs_client = make_gcs_client({"file.txt": text}, encoding="latin-1")

        with patch_gcs(gcs_client):
            loader = GCSLoader(BUCKET, encoding="latin-1")

        (chunk,) = loader.load_keys(["file.txt"])
        assert chunk.content == text

    def test_empty_keys_returns_empty_list(self) -> None:
        with patch_gcs(make_gcs_client({})):
            loader = GCSLoader(BUCKET)

        assert loader.load_keys([]) == []


class TestGCSLoaderLoad:
    def test_load_returns_all_objects(self) -> None:
        objects = {"a.txt": "aaa", "b.txt": "bbb", "c.txt": "ccc"}
        gcs_client = make_gcs_client(objects)

        with patch_gcs(gcs_client):
            loader = GCSLoader(BUCKET)

        chunks = loader.load()

        assert len(chunks) == 3
        assert {c.content for c in chunks} == {"aaa", "bbb", "ccc"}

    def test_load_passes_prefix_to_list_blobs(self) -> None:
        gcs_client = make_gcs_client({"docs/a.txt": "aaa"})

        with patch_gcs(gcs_client):
            loader = GCSLoader(BUCKET)

        loader.load(prefix="docs/")

        gcs_client.list_blobs.assert_called_once_with(BUCKET, prefix="docs/")

    def test_load_without_prefix_omits_prefix_kwarg(self) -> None:
        gcs_client = make_gcs_client({"a.txt": "aaa"})

        with patch_gcs(gcs_client):
            loader = GCSLoader(BUCKET)

        loader.load()

        gcs_client.list_blobs.assert_called_once_with(BUCKET)

    def test_empty_bucket_returns_empty_list(self) -> None:
        gcs_client = make_gcs_client({})
        gcs_client.list_blobs.return_value = []

        with patch_gcs(gcs_client):
            loader = GCSLoader(BUCKET)

        assert loader.load() == []


@pytest.mark.asyncio
class TestGCSLoaderAsync:
    async def test_aload_returns_same_chunks_as_load(self) -> None:
        gcs_client = make_gcs_client({"file.txt": "hello"})

        with patch_gcs(gcs_client):
            loader = GCSLoader(BUCKET)

        sync_chunks = loader.load()
        async_chunks = await loader.aload()

        assert len(async_chunks) == len(sync_chunks)
        assert async_chunks[0].content == sync_chunks[0].content

    async def test_aload_keys_returns_same_chunks_as_load_keys(self) -> None:
        gcs_client = make_gcs_client({"file.txt": "hello"})

        with patch_gcs(gcs_client):
            loader = GCSLoader(BUCKET)

        sync_chunks = loader.load_keys(["file.txt"])
        async_chunks = await loader.aload_keys(["file.txt"])

        assert len(async_chunks) == len(sync_chunks)
        assert async_chunks[0].content == sync_chunks[0].content
