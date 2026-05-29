"""Unit tests for AzureBlobLoader."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from railtracks.retrieval.models import Document

from .conftest import make_container_client_for_loading, patch_azure

ACCOUNT_URL = "https://myaccount.blob.core.windows.net"
CONTAINER = "my-container"


# ---------------------------------------------------------------------------
# AzureBlobLoader
# ---------------------------------------------------------------------------


class TestAzureBlobLoaderInit:
    def test_raises_import_error_when_azure_storage_blob_missing(self) -> None:
        from railtracks.retrieval.loaders.cloud.azure_blob import AzureBlobLoader

        with patch.dict(sys.modules, {"azure.storage.blob": None}):
            with pytest.raises(ImportError, match="azure-storage-blob"):
                AzureBlobLoader(ACCOUNT_URL, CONTAINER)

    def test_import_error_message_mentions_extra(self) -> None:
        from railtracks.retrieval.loaders.cloud.azure_blob import AzureBlobLoader

        with patch.dict(sys.modules, {"azure.storage.blob": None}):
            with pytest.raises(ImportError, match="railtracks\\[azure-blob\\]"):
                AzureBlobLoader(ACCOUNT_URL, CONTAINER)

    def test_trailing_slash_stripped_from_account_url(self) -> None:
        from railtracks.retrieval.loaders.cloud.azure_blob import AzureBlobLoader

        cc = make_container_client_for_loading({})
        with patch_azure(cc):
            loader = AzureBlobLoader(ACCOUNT_URL + "/", CONTAINER)
        assert loader._account_url == ACCOUNT_URL

    def test_explicit_credential_bypasses_default_azure_credential(self) -> None:
        from railtracks.retrieval.loaders.cloud.azure_blob import AzureBlobLoader

        cc = make_container_client_for_loading({})
        explicit_cred = MagicMock()
        with patch_azure(cc):
            import azure.identity as ai  # type: ignore[import]

            AzureBlobLoader(ACCOUNT_URL, CONTAINER, credential=explicit_cred)
            ai.DefaultAzureCredential.assert_not_called()


class TestAzureBlobLoaderKeys:
    def test_returns_document_for_each_blob(self) -> None:
        from railtracks.retrieval.loaders.cloud.azure_blob import AzureBlobLoader

        blobs = {"doc1.txt": "hello", "doc2.txt": "world"}
        cc = make_container_client_for_loading(blobs)
        with patch_azure(cc):
            loader = AzureBlobLoader(ACCOUNT_URL, CONTAINER, keys=list(blobs.keys()))

        docs = loader.load()
        assert len(docs) == 2
        assert all(isinstance(d, Document) for d in docs)

    def test_document_source_contains_full_uri(self) -> None:
        from railtracks.retrieval.loaders.cloud.azure_blob import AzureBlobLoader

        cc = make_container_client_for_loading({"file.txt": "data"})
        with patch_azure(cc):
            loader = AzureBlobLoader(ACCOUNT_URL, CONTAINER, keys=["file.txt"])

        (doc,) = loader.load()
        assert doc.source == f"{ACCOUNT_URL}/{CONTAINER}/file.txt"
        assert doc.metadata["container"] == CONTAINER
        assert doc.metadata["blob_name"] == "file.txt"

    def test_custom_encoding(self) -> None:
        from railtracks.retrieval.loaders.cloud.azure_blob import AzureBlobLoader

        text = "café"
        cc = make_container_client_for_loading({"file.txt": text}, encoding="latin-1")
        with patch_azure(cc):
            loader = AzureBlobLoader(
                ACCOUNT_URL, CONTAINER, keys=["file.txt"], encoding="latin-1"
            )

        (doc,) = loader.load()
        assert doc.content == text


class TestAzureBlobLoaderList:
    def test_load_returns_all_blobs(self) -> None:
        from railtracks.retrieval.loaders.cloud.azure_blob import AzureBlobLoader

        blobs = {"a.txt": "aaa", "b.txt": "bbb"}
        cc = make_container_client_for_loading(blobs)
        with patch_azure(cc):
            loader = AzureBlobLoader(ACCOUNT_URL, CONTAINER)

        docs = loader.load()
        assert len(docs) == 2
        assert {d.content for d in docs} == {"aaa", "bbb"}

    def test_prefix_passed_to_list_blobs(self) -> None:
        from railtracks.retrieval.loaders.cloud.azure_blob import AzureBlobLoader

        cc = make_container_client_for_loading({"docs/a.txt": "aaa"})
        with patch_azure(cc):
            loader = AzureBlobLoader(ACCOUNT_URL, CONTAINER, prefix="docs/")

        loader.load()
        cc.list_blobs.assert_called_once_with(name_starts_with="docs/")

    def test_no_prefix_omits_name_starts_with(self) -> None:
        from railtracks.retrieval.loaders.cloud.azure_blob import AzureBlobLoader

        cc = make_container_client_for_loading({"a.txt": "aaa"})
        with patch_azure(cc):
            loader = AzureBlobLoader(ACCOUNT_URL, CONTAINER)

        loader.load()
        cc.list_blobs.assert_called_once_with()


@pytest.mark.asyncio
class TestAzureBlobLoaderAsync:
    async def test_aload(self) -> None:
        from railtracks.retrieval.loaders.cloud.azure_blob import AzureBlobLoader

        cc = make_container_client_for_loading({"file.txt": "hello"})
        with patch_azure(cc):
            loader = AzureBlobLoader(ACCOUNT_URL, CONTAINER, keys=["file.txt"])

        docs = await loader.aload()
        assert len(docs) == 1
        assert docs[0].content == "hello"
