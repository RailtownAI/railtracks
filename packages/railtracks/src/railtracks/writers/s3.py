from __future__ import annotations

from typing import Callable, Optional

from railtracks.vector_stores.chunking.base_chunker import Chunk

from .base import BaseStorageWriter


class S3Writer(BaseStorageWriter):
    """Document writer for AWS S3.

    Writes text content to an S3 bucket, encoding each object with the
    configured text encoding and returning the full ``s3://`` URI of every
    object written.

    Credentials follow boto3's standard resolution chain: environment variables
    (``AWS_ACCESS_KEY_ID`` / ``AWS_SECRET_ACCESS_KEY``), ``~/.aws/credentials``,
    IAM instance profiles, etc. Pass explicit credentials to override.

    Requires the ``aws`` extra: ``pip install railtracks[aws]``.

    Args:
        bucket: S3 bucket name.
        region_name: AWS region (optional).
        aws_access_key_id: Explicit access key ID (optional).
        aws_secret_access_key: Explicit secret access key (optional).
        aws_session_token: Explicit session token for temporary credentials (optional).
        endpoint_url: Custom endpoint URL for S3-compatible services such as MinIO (optional).
        encoding: Text encoding used when converting content to bytes. Defaults to ``"utf-8"``.
        content_type: MIME type set on the uploaded object. Defaults to
            ``"text/plain; charset=utf-8"``.
        key_fn: Optional callable ``(chunk) -> str`` that derives a storage key
            from a :class:`Chunk`. When ``None`` the key falls back to
            ``chunk.id``, then ``chunk.document``, then a random UUID.

    Raises:
        ImportError: If ``boto3`` is not installed.

    Example::

        writer = S3Writer("my-bucket", region_name="us-east-1")

        # Write a list of Chunk objects
        uris = writer.write(chunks, prefix="generated/")

        # Write raw text at an explicit key
        uri = writer.write_key("reports/summary.txt", "Today's summary ...")

        # Async usage
        uris = await writer.awrite(chunks, prefix="generated/")
    """

    def __init__(
        self,
        bucket: str,
        *,
        region_name: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        encoding: str = "utf-8",
        content_type: str = "text/plain; charset=utf-8",
        key_fn: Optional[Callable[[Chunk], str]] = None,
    ) -> None:
        try:
            import boto3
        except ImportError:
            raise ImportError(
                "boto3 is required for S3 writing. "
                "Install it via `pip install railtracks[aws]` or `uv add railtracks[aws]`."
            )

        self._bucket = bucket
        self._encoding = encoding
        self._content_type = content_type
        self._key_fn = key_fn
        self._client = boto3.client(
            "s3",
            region_name=region_name,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
            endpoint_url=endpoint_url,
        )

    def __repr__(self) -> str:
        return f"S3Writer(bucket={self._bucket!r})"

    def write(self, chunks: list[Chunk], prefix: Optional[str] = None) -> list[str]:
        """Write chunks to S3, one object per chunk.

        Args:
            chunks: Chunk objects to persist.
            prefix: Optional S3 key prefix prepended to each derived key.

        Returns:
            list[str]: ``s3://bucket/key`` URIs of every object written.
        """
        uris: list[str] = []
        for chunk in chunks:
            key = self._derive_key(chunk, prefix, self._key_fn)
            uri = self.write_key(key, chunk.content)
            uris.append(uri)
        return uris

    def write_key(self, key: str, content: str) -> str:
        """Write raw text to S3 at an explicit key.

        Args:
            key: S3 object key (path within the bucket).
            content: Text content to upload.

        Returns:
            str: ``s3://bucket/key`` URI of the written object.
        """
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=content.encode(self._encoding),
            ContentType=self._content_type,
        )
        return f"s3://{self._bucket}/{key}"
