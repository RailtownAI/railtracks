from __future__ import annotations

from typing import Any, Optional

from railtracks.vector_stores.chunking.base_chunker import Chunk

from .base import BaseStorageLoader


class S3Loader(BaseStorageLoader):
    """Document loader for AWS S3.

    Fetches objects from an S3 bucket and returns them as
    :class:`~railtracks.vector_stores.chunking.base_chunker.Chunk` objects
    with UTF-8 decoded content and source metadata.

    Credentials follow boto3's standard resolution chain: environment variables
    (``AWS_ACCESS_KEY_ID`` / ``AWS_SECRET_ACCESS_KEY``), ``~/.aws/credentials``,
    IAM instance profiles, etc. Pass explicit credentials to override the chain.

    Requires the ``aws`` extra: ``pip install railtracks[aws]``.

    Args:
        bucket: S3 bucket name.
        region_name: AWS region (optional).
        aws_access_key_id: Explicit access key ID (optional).
        aws_secret_access_key: Explicit secret access key (optional).
        aws_session_token: Explicit session token for temporary credentials (optional).
        endpoint_url: Custom endpoint URL for S3-compatible services such as MinIO (optional).
        encoding: Text encoding used to decode object bytes. Defaults to ``"utf-8"``.

    Raises:
        ImportError: If ``boto3`` is not installed.

    Example::

        loader = S3Loader("my-bucket", region_name="us-west-2")

        # Load all objects under a prefix
        chunks = loader.load(prefix="documents/")

        # Load specific keys
        chunks = loader.load_keys(["readme.txt", "data/report.txt"])

        # Async usage
        chunks = await loader.aload(prefix="documents/")
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
    ) -> None:
        try:
            import boto3
        except ImportError:
            raise ImportError(
                "boto3 is required for S3 loading. "
                "Install it via `pip install railtracks[aws]` or `uv add railtracks[aws]`."
            )

        self._bucket = bucket
        self._encoding = encoding
        self._client = boto3.client(
            "s3",
            region_name=region_name,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
            endpoint_url=endpoint_url,
        )

    def __repr__(self) -> str:
        return f"S3Loader(bucket={self._bucket!r})"

    def load(self, prefix: Optional[str] = None) -> list[Chunk]:
        """Load all objects from the bucket, optionally filtered by prefix.

        Uses the S3 list-objects paginator so buckets with more than 1 000
        objects are handled correctly.

        Args:
            prefix: Optional S3 key prefix. Only objects whose keys start with
                this string are loaded.

        Returns:
            list[Chunk]: All matching objects as Chunk objects.
        """
        kwargs: dict[str, Any] = {"Bucket": self._bucket}
        if prefix is not None:
            kwargs["Prefix"] = prefix

        keys: list[str] = []
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(**kwargs):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])

        return self.load_keys(keys)

    def load_keys(self, keys: list[str]) -> list[Chunk]:
        """Load specific objects from the bucket by key.

        Args:
            keys: List of S3 object keys to load.

        Returns:
            list[Chunk]: Specified objects as Chunk objects.
        """
        chunks: list[Chunk] = []
        for key in keys:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            content = response["Body"].read().decode(self._encoding)
            chunks.append(
                Chunk(
                    content=content,
                    document=key,
                    metadata={
                        "source": f"s3://{self._bucket}/{key}",
                        "bucket": self._bucket,
                        "key": key,
                    },
                )
            )
        return chunks
