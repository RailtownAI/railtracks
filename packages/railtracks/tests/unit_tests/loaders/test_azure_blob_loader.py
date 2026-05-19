import sys
from unittest.mock import MagicMock, patch

import pytest

from railtracks.loaders.azure_blob import AzureBlobLoader
from railtracks.vector_stores.chunking.base_chunker import Chunk

from .conftest import make_container_client, patch_azure

ACCOUNT_URL = "https://myaccount.blob.core.windows.net"
CONTAINER = "my-container"


class TestAzureBlobLoaderInit:
    def test_raises_import_error_when_azure_storage_blob_missing(self) -> None:
        with patch.dict(sys.modules, {"azure.storage.blob": None}):
            with pytest.raises(ImportError, match="azure-storage-blob"):
                AzureBlobLoader(ACCOUNT_URL, CONTAINER)

    def test_import_error_message_mentions_extra(self) -> None:
        with patch.dict(sys.modules, {"azure.storage.blob": None}):
            with pytest.raises(ImportError, match="railtracks\\[azure-blob\\]"):
                AzureBlobLoader(ACCOUNT_URL, CONTAINER)

    def test_trailing_slash_stripped_from_account_url(self) -> None:
        container_client = make_container_client({})
        with patch_azure(container_client):
            loader = AzureBlobLoader(ACCOUNT_URL + "/", CONTAINER)
        assert loader._account_url == ACCOUNT_URL

    def test_explicit_credential_bypasses_default_azure_credential(self) -> None:
        container_client = make_container_client({})
        explicit_cred = MagicMock()

        with patch_azure(container_client):
            import azure.identity as ai  # type: ignore[import]

            loader = AzureBlobLoader(ACCOUNT_URL, CONTAINER, credential=explicit_cred)
            ai.DefaultAzureCredential.assert_not_called()


class TestAzureBlobLoaderLoadKeys:
    def test_returns_chunk_for_each_blob(self) -> None:
        blobs = {"doc1.txt": "hello", "doc2.txt": "world"}
        container_client = make_container_client(blobs)

        with patch_azure(container_client):
            loader = AzureBlobLoader(ACCOUNT_URL, CONTAINER)

        chunks = loader.load_keys(list(blobs.keys()))

        assert len(chunks) == 2
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_chunk_content_matches_blob_body(self) -> None:
        container_client = make_container_client({"readme.txt": "important content"})

        with patch_azure(container_client):
            loader = AzureBlobLoader(ACCOUNT_URL, CONTAINER)

        (chunk,) = loader.load_keys(["readme.txt"])
        assert chunk.content == "important content"

    def test_chunk_document_is_blob_name(self) -> None:
        container_client = make_container_client({"path/to/file.txt": "data"})

        with patch_azure(container_client):
            loader = AzureBlobLoader(ACCOUNT_URL, CONTAINER)

        (chunk,) = loader.load_keys(["path/to/file.txt"])
        assert chunk.document == "path/to/file.txt"

    def test_chunk_metadata_source_url(self) -> None:
        container_client = make_container_client({"file.txt": "data"})

        with patch_azure(container_client):
            loader = AzureBlobLoader(ACCOUNT_URL, CONTAINER)

        (chunk,) = loader.load_keys(["file.txt"])
        assert chunk.metadata["source"] == f"{ACCOUNT_URL}/{CONTAINER}/file.txt"
        assert chunk.metadata["container"] == CONTAINER
        assert chunk.metadata["blob_name"] == "file.txt"
        assert chunk.metadata["account_url"] == ACCOUNT_URL

    def test_custom_encoding_is_used(self) -> None:
        text = "café"
        container_client = make_container_client({"file.txt": text}, encoding="latin-1")

        with patch_azure(container_client):
            loader = AzureBlobLoader(ACCOUNT_URL, CONTAINER, encoding="latin-1")

        (chunk,) = loader.load_keys(["file.txt"])
        assert chunk.content == text

    def test_empty_keys_returns_empty_list(self) -> None:
        with patch_azure(make_container_client({})):
            loader = AzureBlobLoader(ACCOUNT_URL, CONTAINER)

        assert loader.load_keys([]) == []


class TestAzureBlobLoaderLoad:
    def test_load_returns_all_blobs(self) -> None:
        blobs = {"a.txt": "aaa", "b.txt": "bbb"}
        container_client = make_container_client(blobs)

        with patch_azure(container_client):
            loader = AzureBlobLoader(ACCOUNT_URL, CONTAINER)

        chunks = loader.load()

        assert len(chunks) == 2
        assert {c.content for c in chunks} == {"aaa", "bbb"}

    def test_load_passes_prefix_to_list_blobs(self) -> None:
        container_client = make_container_client({"docs/a.txt": "aaa"})

        with patch_azure(container_client):
            loader = AzureBlobLoader(ACCOUNT_URL, CONTAINER)

        loader.load(prefix="docs/")

        container_client.list_blobs.assert_called_once_with(name_starts_with="docs/")

    def test_load_without_prefix_omits_name_starts_with(self) -> None:
        container_client = make_container_client({"a.txt": "aaa"})

        with patch_azure(container_client):
            loader = AzureBlobLoader(ACCOUNT_URL, CONTAINER)

        loader.load()

        container_client.list_blobs.assert_called_once_with()

    def test_empty_container_returns_empty_list(self) -> None:
        container_client = make_container_client({})
        container_client.list_blobs.return_value = []

        with patch_azure(container_client):
            loader = AzureBlobLoader(ACCOUNT_URL, CONTAINER)

        assert loader.load() == []


@pytest.mark.asyncio
class TestAzureBlobLoaderAsync:
    async def test_aload_returns_same_chunks_as_load(self) -> None:
        container_client = make_container_client({"file.txt": "hello"})

        with patch_azure(container_client):
            loader = AzureBlobLoader(ACCOUNT_URL, CONTAINER)

        sync_chunks = loader.load()
        async_chunks = await loader.aload()

        assert len(async_chunks) == len(sync_chunks)
        assert async_chunks[0].content == sync_chunks[0].content

    async def test_aload_keys_returns_same_chunks_as_load_keys(self) -> None:
        container_client = make_container_client({"file.txt": "hello"})

        with patch_azure(container_client):
            loader = AzureBlobLoader(ACCOUNT_URL, CONTAINER)

        sync_chunks = loader.load_keys(["file.txt"])
        async_chunks = await loader.aload_keys(["file.txt"])

        assert len(async_chunks) == len(sync_chunks)
        assert async_chunks[0].content == sync_chunks[0].content
