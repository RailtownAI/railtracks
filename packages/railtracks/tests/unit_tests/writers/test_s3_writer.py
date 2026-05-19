"""Unit tests for S3Writer."""

import pytest

from railtracks.vector_stores.chunking.base_chunker import Chunk

from .conftest import make_s3_client, patch_s3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_chunk(id_=None, document=None, content="hello world"):
    return Chunk(content=content, id=id_, document=document)


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


class TestInit:
    def test_missing_boto3_raises(self, monkeypatch):
        import sys

        monkeypatch.setitem(sys.modules, "boto3", None)
        with pytest.raises(ImportError, match="boto3"):
            from railtracks.writers.s3 import S3Writer

            S3Writer("my-bucket")


# ---------------------------------------------------------------------------
# write_key
# ---------------------------------------------------------------------------


class TestWriteKey:
    def test_puts_object_at_key(self):
        client = make_s3_client()
        with patch_s3(client):
            from railtracks.writers.s3 import S3Writer

            writer = S3Writer("my-bucket")
            uri = writer.write_key("docs/hello.txt", "hello world")

        assert uri == "s3://my-bucket/docs/hello.txt"
        client.put_object.assert_called_once_with(
            Bucket="my-bucket",
            Key="docs/hello.txt",
            Body=b"hello world",
            ContentType="text/plain; charset=utf-8",
        )

    def test_custom_encoding(self):
        client = make_s3_client()
        with patch_s3(client):
            from railtracks.writers.s3 import S3Writer

            writer = S3Writer("my-bucket", encoding="latin-1")
            writer.write_key("file.txt", "caf\xe9")

        _call = client.put_object.call_args
        assert _call.kwargs["Body"] == "caf\xe9".encode("latin-1")

    def test_custom_content_type(self):
        client = make_s3_client()
        with patch_s3(client):
            from railtracks.writers.s3 import S3Writer

            writer = S3Writer("my-bucket", content_type="application/json")
            writer.write_key("data.json", "{}")

        assert client.put_object.call_args.kwargs["ContentType"] == "application/json"


# ---------------------------------------------------------------------------
# write
# ---------------------------------------------------------------------------


class TestWrite:
    def test_writes_all_chunks(self):
        chunks = [make_chunk(id_=f"doc-{i}", content=f"content {i}") for i in range(3)]
        client = make_s3_client()
        with patch_s3(client):
            from railtracks.writers.s3 import S3Writer

            writer = S3Writer("my-bucket")
            uris = writer.write(chunks)

        assert len(uris) == 3
        assert client.put_object.call_count == 3

    def test_key_from_chunk_id(self):
        chunk = make_chunk(id_="my-id", document="my-doc")
        client = make_s3_client()
        with patch_s3(client):
            from railtracks.writers.s3 import S3Writer

            writer = S3Writer("my-bucket")
            uris = writer.write([chunk])

        assert uris[0] == "s3://my-bucket/my-id"
        client.put_object.assert_called_once()
        assert client.put_object.call_args.kwargs["Key"] == "my-id"

    def test_key_uses_auto_uuid_when_no_explicit_id(self):
        # Chunk always auto-generates a UUID id in __post_init__
        chunk = make_chunk(id_=None, document="ignored")
        client = make_s3_client()
        with patch_s3(client):
            from railtracks.writers.s3 import S3Writer

            writer = S3Writer("my-bucket")
            writer.write([chunk])

        key = client.put_object.call_args.kwargs["Key"]
        assert len(key) == 36  # UUID4 format

    def test_prefix_prepended_to_key(self):
        chunk = make_chunk(id_="doc.txt")
        client = make_s3_client()
        with patch_s3(client):
            from railtracks.writers.s3 import S3Writer

            writer = S3Writer("my-bucket")
            uris = writer.write([chunk], prefix="generated/")

        assert client.put_object.call_args.kwargs["Key"] == "generated/doc.txt"
        assert uris[0] == "s3://my-bucket/generated/doc.txt"

    def test_custom_key_fn(self):
        chunk = make_chunk(id_="ignore-this")
        client = make_s3_client()
        with patch_s3(client):
            from railtracks.writers.s3 import S3Writer

            writer = S3Writer("my-bucket", key_fn=lambda c: "custom-key.txt")
            writer.write([chunk])

        assert client.put_object.call_args.kwargs["Key"] == "custom-key.txt"

    def test_returns_correct_uris(self):
        chunks = [make_chunk(id_="a"), make_chunk(id_="b")]
        client = make_s3_client()
        with patch_s3(client):
            from railtracks.writers.s3 import S3Writer

            writer = S3Writer("bucket-x")
            uris = writer.write(chunks)

        assert uris == ["s3://bucket-x/a", "s3://bucket-x/b"]

    def test_empty_chunks(self):
        client = make_s3_client()
        with patch_s3(client):
            from railtracks.writers.s3 import S3Writer

            writer = S3Writer("my-bucket")
            uris = writer.write([])

        assert uris == []
        client.put_object.assert_not_called()


# ---------------------------------------------------------------------------
# Async
# ---------------------------------------------------------------------------


class TestAsync:
    @pytest.mark.asyncio
    async def test_awrite_delegates_to_write(self):
        chunks = [make_chunk(id_="x")]
        client = make_s3_client()
        with patch_s3(client):
            from railtracks.writers.s3 import S3Writer

            writer = S3Writer("my-bucket")
            uris = await writer.awrite(chunks)

        assert uris == ["s3://my-bucket/x"]

    @pytest.mark.asyncio
    async def test_awrite_key_delegates(self):
        client = make_s3_client()
        with patch_s3(client):
            from railtracks.writers.s3 import S3Writer

            writer = S3Writer("my-bucket")
            uri = await writer.awrite_key("k.txt", "data")

        assert uri == "s3://my-bucket/k.txt"
