from __future__ import annotations

from typing import Any, Optional

from railtracks.vector_stores.chunking.base_chunker import Chunk

from .base import BaseStorageLoader


class GCSLoader(BaseStorageLoader):
    """Document loader for Google Cloud Storage (GCS).

    Fetches objects from a GCS bucket and returns them as
    :class:`~railtracks.vector_stores.chunking.base_chunker.Chunk` objects
    with UTF-8 decoded content and source metadata.

    Authentication uses **Application Default Credentials (ADC)** by default,
    which resolves credentials from the following sources (in order):

    1. ``GOOGLE_APPLICATION_CREDENTIALS`` environment variable (path to a
       service-account JSON key file)
    2. ``gcloud auth application-default login`` (developer workstation)
    3. Workload Identity / attached service account (GCE, GKE, Cloud Run …)

    Pass explicit ``credentials`` to override ADC.

    Requires the ``gcp`` extra: ``pip install railtracks[gcp]``.

    Args:
        bucket_name: GCS bucket name.
        project: Google Cloud project ID. Inferred from ADC when ``None``.
        credentials: Explicit Google credential object (e.g.
            ``google.oauth2.service_account.Credentials``). Defaults to ADC.
        encoding: Text encoding used to decode object bytes. Defaults to ``"utf-8"``.

    Raises:
        ImportError: If ``google-cloud-storage`` is not installed.

    Example::

        loader = GCSLoader("my-bucket", project="my-gcp-project")

        # Load all objects under a prefix
        chunks = loader.load(prefix="documents/")

        # Load specific object names
        chunks = loader.load_keys(["readme.txt", "data/report.txt"])

        # Async usage
        chunks = await loader.aload(prefix="documents/")
    """

    def __init__(
        self,
        bucket_name: str,
        *,
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
        self._encoding = encoding
        self._client = storage.Client(project=project, credentials=credentials)

    def __repr__(self) -> str:
        return f"GCSLoader(bucket_name={self._bucket_name!r})"

    def load(self, prefix: Optional[str] = None) -> list[Chunk]:
        """Load all objects from the bucket, optionally filtered by prefix.

        Args:
            prefix: Optional object name prefix. Only objects whose names start
                with this string are loaded.

        Returns:
            list[Chunk]: All matching objects as Chunk objects.
        """
        kwargs: dict[str, Any] = {}
        if prefix is not None:
            kwargs["prefix"] = prefix

        blob_names = [
            blob.name
            for blob in self._client.list_blobs(self._bucket_name, **kwargs)
        ]
        return self.load_keys(blob_names)

    def load_keys(self, keys: list[str]) -> list[Chunk]:
        """Load specific objects from the bucket by name.

        Args:
            keys: List of GCS object names to load.

        Returns:
            list[Chunk]: Specified objects as Chunk objects.
        """
        bucket = self._client.bucket(self._bucket_name)
        chunks: list[Chunk] = []
        for name in keys:
            blob = bucket.blob(name)
            content = blob.download_as_bytes().decode(self._encoding)
            chunks.append(
                Chunk(
                    content=content,
                    document=name,
                    metadata={
                        "source": f"gs://{self._bucket_name}/{name}",
                        "bucket": self._bucket_name,
                        "name": name,
                    },
                )
            )
        return chunks
