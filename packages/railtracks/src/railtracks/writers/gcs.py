from __future__ import annotations

from typing import Any, Callable, Optional

from railtracks.vector_stores.chunking.base_chunker import Chunk

from .base import BaseStorageWriter


class GCSWriter(BaseStorageWriter):
    """Document writer for Google Cloud Storage (GCS).

    Uploads text content to a GCS bucket, encoding each object with the
    configured text encoding and returning the full ``gs://`` URI of every
    object written.  Existing objects at the same name are overwritten.

    Authentication uses **Application Default Credentials (ADC)** by default,
    which resolves credentials from the following sources (in order):

    1. ``GOOGLE_APPLICATION_CREDENTIALS`` environment variable
    2. ``gcloud auth application-default login`` (developer workstation)
    3. Workload Identity / attached service account (GCE, GKE, Cloud Run ...)

    Pass explicit ``credentials`` to override ADC.

    Requires the ``gcp`` extra: ``pip install railtracks[gcp]``.

    Args:
        bucket_name: GCS bucket name.
        project: Google Cloud project ID. Inferred from ADC when ``None``.
        credentials: Explicit Google credential object. Defaults to ADC.
        encoding: Text encoding used when converting content to bytes. Defaults to ``"utf-8"``.
        content_type: MIME type set on the uploaded object. Defaults to
            ``"text/plain; charset=utf-8"``.
        key_fn: Optional callable ``(chunk) -> str`` that derives a storage key
            from a :class:`Chunk`. When ``None`` the name falls back to
            ``chunk.id``, then ``chunk.document``, then a random UUID.

    Raises:
        ImportError: If ``google-cloud-storage`` is not installed.

    Example::

        writer = GCSWriter("my-bucket", project="my-gcp-project")

        # Write a list of Chunk objects
        uris = writer.write(chunks, prefix="generated/")

        # Write raw text at an explicit object name
        uri = writer.write_key("reports/summary.txt", "Today's summary ...")

        # Async usage
        uris = await writer.awrite(chunks, prefix="generated/")
    """

    def __init__(
        self,
        bucket_name: str,
        *,
        project: Optional[str] = None,
        credentials: Optional[Any] = None,
        encoding: str = "utf-8",
        content_type: str = "text/plain; charset=utf-8",
        key_fn: Optional[Callable[[Chunk], str]] = None,
    ) -> None:
        try:
            from google.cloud import storage  # type: ignore[import]
        except ImportError:
            raise ImportError(
                "google-cloud-storage is required for GCS writing. "
                "Install it via `pip install railtracks[gcp]` or `uv add railtracks[gcp]`."
            )

        self._bucket_name = bucket_name
        self._encoding = encoding
        self._content_type = content_type
        self._key_fn = key_fn
        self._client = storage.Client(project=project, credentials=credentials)

    def __repr__(self) -> str:
        return f"GCSWriter(bucket_name={self._bucket_name!r})"

    def write(self, chunks: list[Chunk], prefix: Optional[str] = None) -> list[str]:
        """Write chunks to GCS, one object per chunk.

        Args:
            chunks: Chunk objects to persist.
            prefix: Optional object name prefix prepended to each derived name.

        Returns:
            list[str]: ``gs://bucket/name`` URIs of every object written.
        """
        uris: list[str] = []
        for chunk in chunks:
            name = self._derive_key(chunk, prefix, self._key_fn)
            uri = self.write_key(name, chunk.content)
            uris.append(uri)
        return uris

    def write_key(self, key: str, content: str) -> str:
        """Write raw text to GCS at an explicit object name.

        Args:
            key: GCS object name (path within the bucket).
            content: Text content to upload.

        Returns:
            str: ``gs://bucket/name`` URI of the written object.
        """
        bucket = self._client.bucket(self._bucket_name)
        blob = bucket.blob(key)
        blob.upload_from_string(
            content.encode(self._encoding),
            content_type=self._content_type,
        )
        return f"gs://{self._bucket_name}/{key}"
