from __future__ import annotations

from typing import Any, Optional

from railtracks.retrieval.loaders._pdf_options import BreakdownStrategy
from railtracks.retrieval.loaders.cloud._common import ObjectStoreLoader


class GCSLoader(ObjectStoreLoader):
    """Document loader for Google Cloud Storage (GCS).

    Fetches objects from a GCS bucket and yields them as :class:`Document`
    instances with source metadata. Listing is recursive — any object
    whose name starts with ``prefix`` is loaded,
    including subfolders.

    Text objects are decoded with ``encoding``. PDFs are parsed with the same
    logic as ``PyPDFLoader`` (requires the ``pdf`` extra), split according to
    ``pdf_breakdown_strategy``. A object that cannot be downloaded or parsed,
    including a ``.txt``, ``.md``, ``.csv``, ``.json`` or ``.jsonl`` object that
    is not valid text, is yielded as a ``LoadFailure`` and the remaining
    objects still load. Any other object that is not valid text, such as an
    image, is skipped with a warning.

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
        pdf_breakdown_strategy: How to split each PDF into ``Document`` objects,
            as in ``PyPDFLoader``: ``"page"`` (default), ``"paragraph"``, or
            ``"document"``.

    Raises:
        ImportError: If ``google-cloud-storage`` is not installed.
        ValueError: If ``pdf_breakdown_strategy`` is not a known strategy.
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
        pdf_breakdown_strategy: BreakdownStrategy = "page",
    ) -> None:
        try:
            from google.cloud import storage  # type: ignore[import]
        except ImportError:
            raise ImportError(
                "google-cloud-storage is required for GCS loading. "
                "Install it via `pip install railtracks[gcp]` or `uv add railtracks[gcp]`."
            )

        super().__init__(
            prefix=prefix,
            keys=keys,
            encoding=encoding,
            pdf_breakdown_strategy=pdf_breakdown_strategy,
        )
        self._bucket_name = bucket_name
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

    def _fetch_bytes(self, key: str) -> bytes:
        bucket = self._client.bucket(self._bucket_name)
        return bucket.blob(key).download_as_bytes()

    def _source(self, key: str) -> str:
        return f"gs://{self._bucket_name}/{key}"

    def _metadata(self, key: str) -> dict[str, str]:
        return {"bucket": self._bucket_name, "name": key}
