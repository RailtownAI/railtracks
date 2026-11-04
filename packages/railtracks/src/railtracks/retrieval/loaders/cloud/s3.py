from __future__ import annotations

from typing import Any, Optional

from railtracks.retrieval.loaders._pdf_options import BreakdownStrategy
from railtracks.retrieval.loaders.cloud._common import ObjectStoreLoader


class S3Loader(ObjectStoreLoader):
    """Document loader for AWS S3.

    Fetches objects from an S3 bucket and yields them as :class:`Document`
    instances with source metadata. Listing is recursive — any object
    whose key starts with ``prefix`` is loaded,
    including those in subfolders (``A/B/file.txt``).

    Text objects are decoded with ``encoding``. PDFs are parsed with the same
    logic as ``PyPDFLoader`` (requires the ``pdf`` extra), split according to
    ``pdf_breakdown_strategy``. A ``.txt``, ``.md``, ``.csv``, ``.json`` or
    ``.jsonl`` object that is not valid text raises; any other object that is
    not valid text, such as an image, is skipped with a warning.

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
        pdf_breakdown_strategy: How to split each PDF into ``Document`` objects,
            as in ``PyPDFLoader``: ``"page"`` (default), ``"paragraph"``, or
            ``"document"``.

    Raises:
        ImportError: If ``boto3`` is not installed.
        ValueError: If ``pdf_breakdown_strategy`` is not a known strategy.

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
        pdf_breakdown_strategy: BreakdownStrategy = "page",
    ) -> None:
        try:
            import boto3
        except ImportError:
            raise ImportError(
                "boto3 is required for S3 loading. "
                "Install it via `pip install railtracks[aws]` or `uv add railtracks[aws]`."
            )

        super().__init__(
            prefix=prefix,
            keys=keys,
            encoding=encoding,
            pdf_breakdown_strategy=pdf_breakdown_strategy,
        )
        self._bucket = bucket
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

    def _fetch_bytes(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        return response["Body"].read()

    def _source(self, key: str) -> str:
        return f"s3://{self._bucket}/{key}"

    def _metadata(self, key: str) -> dict[str, str]:
        return {"bucket": self._bucket, "key": key}
