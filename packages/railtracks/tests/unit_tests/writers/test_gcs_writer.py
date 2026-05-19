"""Unit tests for GCSWriter."""

import pytest

from railtracks.vector_stores.chunking.base_chunker import Chunk

from .conftest import make_gcs_client, patch_gcs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_chunk(id_=None, document=None, content="hello world"):
    return Chunk(content=content, id=id_, document=document)


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


class TestInit:
    def test_missing_gcs_raises(self, monkeypatch):
        import sys

        monkeypatch.setitem(sys.modules, "google.cloud.storage", None)
        monkeypatch.setitem(sys.modules, "google.cloud", None)
        with pytest.raises(ImportError, match="google-cloud-storage"):
            from railtracks.writers.gcs import GCSWriter

            GCSWriter("my-bucket")

    def test_credentials_forwarded(self):
        client = make_gcs_client()
        with patch_gcs(client) as mock_storage:
            from railtracks.writers.gcs import GCSWriter

            creds = object()
            GCSWriter("my-bucket", credentials=creds, project="proj")

            mock_storage.Client.assert_called_once_with(
                project="proj", credentials=creds
            )


# ---------------------------------------------------------------------------
# write_key
# ---------------------------------------------------------------------------


class TestWriteKey:
    def test_uploads_object(self):
        client = make_gcs_client()
        with patch_gcs(client):
            from railtracks.writers.gcs import GCSWriter

            writer = GCSWriter("my-bucket")
            uri = writer.write_key("docs/hello.txt", "hello world")

        assert uri == "gs://my-bucket/docs/hello.txt"
        assert client._written["docs/hello.txt"] == b"hello world"

    def test_custom_encoding(self):
        client = make_gcs_client()
        with patch_gcs(client):
            from railtracks.writers.gcs import GCSWriter

            writer = GCSWriter("my-bucket", encoding="latin-1")
            writer.write_key("f.txt", "caf\xe9")

        assert client._written["f.txt"] == "caf\xe9".encode("latin-1")

    def test_content_type_passed(self):
        client = make_gcs_client()
        with patch_gcs(client):
            from railtracks.writers.gcs import GCSWriter

            writer = GCSWriter("my-bucket", content_type="application/json")
            writer.write_key("data.json", "{}")

        assert client._content_types["data.json"] == "application/json"


# ---------------------------------------------------------------------------
# write
# ---------------------------------------------------------------------------


class TestWrite:
    def test_writes_all_chunks(self):
        chunks = [make_chunk(id_=f"doc-{i}") for i in range(3)]
        client = make_gcs_client()
        with patch_gcs(client):
            from railtracks.writers.gcs import GCSWriter

            writer = GCSWriter("my-bucket")
            uris = writer.write(chunks)

        assert len(uris) == 3
        assert len(client._written) == 3

    def test_key_from_chunk_id(self):
        chunk = make_chunk(id_="my-id", document="my-doc")
        client = make_gcs_client()
        with patch_gcs(client):
            from railtracks.writers.gcs import GCSWriter

            writer = GCSWriter("my-bucket")
            uris = writer.write([chunk])

        assert "my-id" in client._written
        assert uris[0] == "gs://my-bucket/my-id"

    def test_key_uses_auto_uuid_when_no_explicit_id(self):
        # Chunk always auto-generates a UUID id in __post_init__
        chunk = make_chunk(id_=None, document="ignored")
        client = make_gcs_client()
        with patch_gcs(client):
            from railtracks.writers.gcs import GCSWriter

            writer = GCSWriter("my-bucket")
            writer.write([chunk])

        key = list(client._written.keys())[0]
        assert len(key) == 36  # UUID4 format

    def test_prefix_prepended(self):
        chunk = make_chunk(id_="report.txt")
        client = make_gcs_client()
        with patch_gcs(client):
            from railtracks.writers.gcs import GCSWriter

            writer = GCSWriter("my-bucket")
            uris = writer.write([chunk], prefix="output/")

        assert "output/report.txt" in client._written
        assert uris[0] == "gs://my-bucket/output/report.txt"

    def test_custom_key_fn(self):
        chunk = make_chunk(id_="ignore")
        client = make_gcs_client()
        with patch_gcs(client):
            from railtracks.writers.gcs import GCSWriter

            writer = GCSWriter("my-bucket", key_fn=lambda c: "custom.txt")
            writer.write([chunk])

        assert "custom.txt" in client._written

    def test_empty_chunks(self):
        client = make_gcs_client()
        with patch_gcs(client):
            from railtracks.writers.gcs import GCSWriter

            writer = GCSWriter("my-bucket")
            uris = writer.write([])

        assert uris == []
        assert client._written == {}

    def test_content_written_correctly(self):
        chunk = make_chunk(id_="doc", content="the quick brown fox")
        client = make_gcs_client()
        with patch_gcs(client):
            from railtracks.writers.gcs import GCSWriter

            writer = GCSWriter("my-bucket")
            writer.write([chunk])

        assert client._written["doc"] == b"the quick brown fox"


# ---------------------------------------------------------------------------
# Async
# ---------------------------------------------------------------------------


class TestAsync:
    @pytest.mark.asyncio
    async def test_awrite(self):
        chunks = [make_chunk(id_="z", content="data")]
        client = make_gcs_client()
        with patch_gcs(client):
            from railtracks.writers.gcs import GCSWriter

            writer = GCSWriter("my-bucket")
            uris = await writer.awrite(chunks)

        assert uris == ["gs://my-bucket/z"]
        assert client._written["z"] == b"data"

    @pytest.mark.asyncio
    async def test_awrite_key(self):
        client = make_gcs_client()
        with patch_gcs(client):
            from railtracks.writers.gcs import GCSWriter

            writer = GCSWriter("my-bucket")
            uri = await writer.awrite_key("k.txt", "content")

        assert uri == "gs://my-bucket/k.txt"
        assert client._written["k.txt"] == b"content"
