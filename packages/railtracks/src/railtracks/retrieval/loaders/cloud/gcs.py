from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any, Optional

from railtracks.retrieval.loaders.base import BaseDocumentLoader
from railtracks.retrieval.loaders.cloud._common import infer_document_type
from railtracks.retrieval.models import Document


class GCSLoader(BaseDocumentLoader):
    """Document loader for Google Cloud Storage (GCS).

    Fetches objects from a GCS bucket and yields them as :class:`Document`
    instances with UTF-8 decoded content and source metadata. Listing is
    recursive — any object whose name starts with ``prefix`` is loaded,
    including subfolders.

    Authentication uses **Application Default Credentials (ADC)** by default,
    which resolves credentials from the following sources (in order):

    1. ``GOOGLE_APPLICATION_CREDENTIALS`` environment variable (path to a
       service-account JSON key file)
    2. ``gcloud auth application-default login`` (developer workstation)
    3. Workload Identity / attached service account (GCE, GKE, Cloud Run ...)

    Pass explicit ``credentials`` to override ADC.

    Requires the ``gcp`` extra: ``pip install railtracks[gcp]``.

    Args:
        bucket_name: GCS bucket name.
        prefix: Optional object name prefix to filter the listing. Ignored
            when ``keys`` is provided.
        keys: Explicit list of object names to load. When set, ``prefix`` is
            ignored.
        project: Google Cloud project ID. Inferred from ADC when ``None``.
        credentials: Explicit Google credential object. Defaults to ADC.
        encoding: Text encoding used to decode object bytes. Defaults to ``"utf-8"``.

    Raises:
        ImportError: If ``google-cloud-storage`` is not installed.
    """

    def __init__(
        self,
        bucket_name: str,
        *,
        prefix: Optional[str] = None,
        keys: Optional[list[str]] = None,
        project: Optional[str] = None,
        credentials: Optional[Any] = None,
        encoding: str = "utf-8",
    ) -> None:
        try:
            from google.cloud import storage  # type: ignore[import]
        except ImportError:
            raise ImportError(
                "google-cloud-storage is required for GCS loading. "
                "Install it via `pip install railtracks[gcp]` or `uv add railtracks[gcp]`."
            )

        self._bucket_name = bucket_name
        self._prefix = prefix
        self._keys = list(keys) if keys is not None else None
        self._encoding = encoding
        self._client = storage.Client(project=project, credentials=credentials)

    def __repr__(self) -> str:
        return f"GCSLoader(bucket_name={self._bucket_name!r})"

    def _list_keys(self) -> list[str]:
        kwargs: dict[str, Any] = {}
        if self._prefix is not None:
            kwargs["prefix"] = self._prefix
        return [
            blob.name for blob in self._client.list_blobs(self._bucket_name, **kwargs)
        ]

    def _fetch_document(self, name: str) -> Document:
        bucket = self._client.bucket(self._bucket_name)
        blob = bucket.blob(name)
        content = blob.download_as_bytes().decode(self._encoding)
        return Document(
            content=content,
            type=infer_document_type(name),
            source=f"gs://{self._bucket_name}/{name}",
            metadata={
                "bucket": self._bucket_name,
                "name": name,
            },
        )

    async def astream(self) -> AsyncGenerator[Document, None]:
        """Stream documents one at a time as each GCS object is downloaded.

        Yields:
            Document: The next loaded document.
        """
        if self._keys is not None:
            names = self._keys
        else:
            names = await asyncio.to_thread(self._list_keys)

        for name in names:
            yield await asyncio.to_thread(self._fetch_document, name)
