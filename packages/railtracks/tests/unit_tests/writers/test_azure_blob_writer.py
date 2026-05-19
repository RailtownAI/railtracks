"""Unit tests for AzureBlobWriter."""

import pytest

from railtracks.vector_stores.chunking.base_chunker import Chunk

from .conftest import make_container_client, patch_azure


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_chunk(id_=None, document=None, content="hello world"):
    return Chunk(content=content, id=id_, document=document)


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


class TestInit:
    def test_missing_azure_raises(self, monkeypatch):
        import sys

        monkeypatch.setitem(sys.modules, "azure.storage.blob", None)
        with pytest.raises(ImportError, match="azure-storage-blob"):
            from railtracks.writers.azure_blob import AzureBlobWriter

            AzureBlobWriter("https://acc.blob.core.windows.net", "container")

    def test_default_credential_used(self):
        cc = make_container_client()
        with patch_azure(cc) as (mock_storage, mock_identity):
            from railtracks.writers.azure_blob import AzureBlobWriter

            AzureBlobWriter("https://acc.blob.core.windows.net", "container")

            mock_identity.DefaultAzureCredential.assert_called_once()

    def test_explicit_credential_skips_default(self):
        cc = make_container_client()
        with patch_azure(cc) as (mock_storage, mock_identity):
            from railtracks.writers.azure_blob import AzureBlobWriter

            AzureBlobWriter(
                "https://acc.blob.core.windows.net",
                "container",
                credential="my-key",
            )
            mock_identity.DefaultAzureCredential.assert_not_called()

    def test_trailing_slash_stripped(self):
        cc = make_container_client()
        with patch_azure(cc):
            from railtracks.writers.azure_blob import AzureBlobWriter

            writer = AzureBlobWriter(
                "https://acc.blob.core.windows.net/",
                "container",
            )
            assert writer._account_url == "https://acc.blob.core.windows.net"


# ---------------------------------------------------------------------------
# write_key
# ---------------------------------------------------------------------------


class TestWriteKey:
    def test_uploads_blob(self):
        cc = make_container_client()
        with patch_azure(cc):
            from railtracks.writers.azure_blob import AzureBlobWriter

            writer = AzureBlobWriter("https://acc.blob.core.windows.net", "ctr")
            uri = writer.write_key("reports/hello.txt", "hello world")

        assert uri == "https://acc.blob.core.windows.net/ctr/reports/hello.txt"
        cc.get_blob_client.assert_called_once_with("reports/hello.txt")
        assert cc._written["reports/hello.txt"] == b"hello world"

    def test_custom_encoding(self):
        cc = make_container_client()
        with patch_azure(cc):
            from railtracks.writers.azure_blob import AzureBlobWriter

            writer = AzureBlobWriter(
                "https://acc.blob.core.windows.net", "ctr", encoding="latin-1"
            )
            writer.write_key("f.txt", "caf\xe9")

        assert cc._written["f.txt"] == "caf\xe9".encode("latin-1")


# ---------------------------------------------------------------------------
# write
# ---------------------------------------------------------------------------


class TestWrite:
    def test_writes_all_chunks(self):
        chunks = [make_chunk(id_=f"blob-{i}") for i in range(3)]
        cc = make_container_client()
        with patch_azure(cc):
            from railtracks.writers.azure_blob import AzureBlobWriter

            writer = AzureBlobWriter("https://acc.blob.core.windows.net", "ctr")
            uris = writer.write(chunks)

        assert len(uris) == 3
        assert cc.get_blob_client.call_count == 3

    def test_key_from_chunk_id(self):
        chunk = make_chunk(id_="my-id", document="my-doc")
        cc = make_container_client()
        with patch_azure(cc):
            from railtracks.writers.azure_blob import AzureBlobWriter

            writer = AzureBlobWriter("https://acc.blob.core.windows.net", "ctr")
            uris = writer.write([chunk])

        cc.get_blob_client.assert_called_once_with("my-id")
        assert uris[0] == "https://acc.blob.core.windows.net/ctr/my-id"

    def test_key_uses_auto_uuid_when_no_explicit_id(self):
        # Chunk always auto-generates a UUID id in __post_init__
        chunk = make_chunk(id_=None, document="ignored")
        cc = make_container_client()
        with patch_azure(cc):
            from railtracks.writers.azure_blob import AzureBlobWriter

            writer = AzureBlobWriter("https://acc.blob.core.windows.net", "ctr")
            uris = writer.write([chunk])

        # chunk.id was auto-assigned a UUID by Chunk.__post_init__
        name = cc.get_blob_client.call_args.args[0]
        assert len(name) == 36  # UUID4 format

    def test_prefix_prepended(self):
        chunk = make_chunk(id_="report.txt")
        cc = make_container_client()
        with patch_azure(cc):
            from railtracks.writers.azure_blob import AzureBlobWriter

            writer = AzureBlobWriter("https://acc.blob.core.windows.net", "ctr")
            uris = writer.write([chunk], prefix="output/")

        cc.get_blob_client.assert_called_once_with("output/report.txt")
        assert uris[0] == "https://acc.blob.core.windows.net/ctr/output/report.txt"

    def test_custom_key_fn(self):
        chunk = make_chunk(id_="ignore")
        cc = make_container_client()
        with patch_azure(cc):
            from railtracks.writers.azure_blob import AzureBlobWriter

            writer = AzureBlobWriter(
                "https://acc.blob.core.windows.net",
                "ctr",
                key_fn=lambda c: "overridden.txt",
            )
            writer.write([chunk])

        cc.get_blob_client.assert_called_once_with("overridden.txt")

    def test_empty_chunks(self):
        cc = make_container_client()
        with patch_azure(cc):
            from railtracks.writers.azure_blob import AzureBlobWriter

            writer = AzureBlobWriter("https://acc.blob.core.windows.net", "ctr")
            uris = writer.write([])

        assert uris == []
        cc.get_blob_client.assert_not_called()


# ---------------------------------------------------------------------------
# Async
# ---------------------------------------------------------------------------


class TestAsync:
    @pytest.mark.asyncio
    async def test_awrite(self):
        chunks = [make_chunk(id_="z")]
        cc = make_container_client()
        with patch_azure(cc):
            from railtracks.writers.azure_blob import AzureBlobWriter

            writer = AzureBlobWriter("https://acc.blob.core.windows.net", "ctr")
            uris = await writer.awrite(chunks)

        assert uris == ["https://acc.blob.core.windows.net/ctr/z"]

    @pytest.mark.asyncio
    async def test_awrite_key(self):
        cc = make_container_client()
        with patch_azure(cc):
            from railtracks.writers.azure_blob import AzureBlobWriter

            writer = AzureBlobWriter("https://acc.blob.core.windows.net", "ctr")
            uri = await writer.awrite_key("k.txt", "data")

        assert uri == "https://acc.blob.core.windows.net/ctr/k.txt"
