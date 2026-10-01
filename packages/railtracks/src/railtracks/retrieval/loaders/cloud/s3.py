from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any, Optional

from railtracks.retrieval.loaders.base import BaseDocumentLoader
from railtracks.retrieval.loaders.cloud._common import infer_document_type
from railtracks.retrieval.models import Document


class S3Loader(BaseDocumentLoader):
    """Document loader for AWS S3.

    Fetches objects from an S3 bucket and yields them as :class:`Document`
    instances with UTF-8 decoded content and source metadata. Listing is
    recursive — any object whose key starts with ``prefix`` is loaded,
    including those in subfolders (``A/B/file.txt``).

    Credentials follow boto3's standard resolution chain: environment variables
    (``AWS_ACCESS_KEY_ID`` / ``AWS_SECRET_ACCESS_KEY``), ``~/.aws/credentials``,
    IAM instance profiles, etc. Pass explicit credentials to override the chain.

    Requires the ``aws`` extra: ``pip install railtracks[aws]``.

    Args:
        bucket: S3 bucket name.
        prefix: Optional S3 key prefix. When set, only objects whose keys start
            with this string are loaded. Ignored when ``keys`` is provided.
        keys: Explicit list of object keys to load. When set, ``prefix`` is
            ignored.
        region_name: AWS region (optional).
        aws_access_key_id: Explicit access key ID (optional).
        aws_secret_access_key: Explicit secret access key (optional).
        aws_session_token: Explicit session token for temporary credentials (optional).
        endpoint_url: Custom endpoint URL for S3-compatible services such as MinIO (optional).
        encoding: Text encoding used to decode object bytes. Defaults to ``"utf-8"``.

    Raises:
        ImportError: If ``boto3`` is not installed.

    Example::

        # Load all objects under a prefix (recursive)
        loader = S3Loader("my-bucket", prefix="documents/")
        documents = loader.load()

        # Load specific keys
        loader = S3Loader("my-bucket", keys=["readme.txt", "data/report.txt"])
        documents = loader.load()

        # Stream documents as they are downloaded
        async for doc in S3Loader("my-bucket", prefix="docs/").astream():
            ...
    """

    def __init__(
        self,
        bucket: str,
        *,
        prefix: Optional[str] = None,
        keys: Optional[list[str]] = None,
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
        self._prefix = prefix
        self._keys = list(keys) if keys is not None else None
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

    def _list_keys(self) -> list[str]:
        kwargs: dict[str, Any] = {"Bucket": self._bucket}
        if self._prefix is not None:
            kwargs["Prefix"] = self._prefix

        keys: list[str] = []
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(**kwargs):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])
        return keys

    def _fetch_document(self, key: str) -> Document:
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        content = response["Body"].read().decode(self._encoding)
        return Document(
            content=content,
            type=infer_document_type(key),
            source=f"s3://{self._bucket}/{key}",
            metadata={
                "bucket": self._bucket,
                "key": key,
            },
        )

    async def astream(self) -> AsyncGenerator[Document, None]:
        """Stream documents one at a time as each S3 object is fetched.

        Yields:
            Document: The next loaded document.
        """
        if self._keys is not None:
            keys = self._keys
        else:
            keys = await asyncio.to_thread(self._list_keys)

        for key in keys:
            yield await asyncio.to_thread(self._fetch_document, key)
