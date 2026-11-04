from __future__ import annotations

from typing import Any, Optional

from railtracks.retrieval.loaders._pdf_options import BreakdownStrategy
from railtracks.retrieval.loaders.cloud._common import ObjectStoreLoader


def _ensure_credential(credential: Optional[Any]) -> Any:
    if credential is not None:
        return credential
    try:
        from azure.identity import DefaultAzureCredential
    except ImportError:
        raise ImportError(
            "azure-identity is required for default credential resolution. "
            "Install it via `pip install railtracks[azure-blob]` or `uv add railtracks[azure-blob]`."
        )
    return DefaultAzureCredential()


class AzureBlobLoader(ObjectStoreLoader):
    """Document loader for Azure Blob Storage.

    Fetches blobs from a container and yields them as :class:`Document`
    instances with source metadata. Listing is recursive — any blob
    whose name starts with ``prefix`` is loaded,
    including subfolders.

    Text objects are decoded with ``encoding``. PDFs are parsed with the same
    logic as ``PyPDFLoader`` (requires the ``pdf`` extra), split according to
    ``pdf_breakdown_strategy``. A ``.txt``, ``.md``, ``.csv``, ``.json`` or
    ``.jsonl`` blob that is not valid text raises; any other blob that is not
    valid text, such as an image, is skipped with a warning.

    Authentication defaults to ``DefaultAzureCredential``, which resolves
    credentials from environment variables, managed identity, the Azure CLI,
    and other standard sources automatically. Pass an explicit ``credential``
    to override.

    Requires the ``azure-blob`` extra: ``pip install railtracks[azure-blob]``.

    Args:
        account_url: Azure Storage account URL, e.g.
            ``"https://<account>.blob.core.windows.net"``.
        container_name: Name of the blob container.
        prefix: Optional blob name prefix to filter the listing. Ignored when
            ``keys`` is provided.
        keys: Explicit list of blob names to load. When set, ``prefix`` is
            ignored.
        credential: Azure credential used for authentication. Defaults to
            ``DefaultAzureCredential()`` when ``None``.
        encoding: Text encoding used to decode blob bytes. Defaults to ``"utf-8"``.
        pdf_breakdown_strategy: How to split each PDF into ``Document`` objects,
            as in ``PyPDFLoader``: ``"page"`` (default), ``"paragraph"``, or
            ``"document"``.

    Raises:
        ImportError: If ``azure-storage-blob`` or ``azure-identity`` are not installed.
        ValueError: If ``pdf_breakdown_strategy`` is not a known strategy.
    """

    def __init__(
        self,
        account_url: str,
        container_name: str,
        *,
        prefix: Optional[str] = None,
        keys: Optional[list[str]] = None,
        credential: Optional[Any] = None,
        encoding: str = "utf-8",
        pdf_breakdown_strategy: BreakdownStrategy = "page",
    ) -> None:
        try:
            from azure.storage.blob import ContainerClient
        except ImportError:
            raise ImportError(
                "azure-storage-blob is required for Azure Blob loading. "
                "Install it via `pip install railtracks[azure-blob]` or `uv add railtracks[azure-blob]`."
            )

        credential = _ensure_credential(credential)

        super().__init__(
            prefix=prefix,
            keys=keys,
            encoding=encoding,
            pdf_breakdown_strategy=pdf_breakdown_strategy,
        )
        self._account_url = account_url.rstrip("/")
        self._container_name = container_name
        self._container_client = ContainerClient(
            account_url=self._account_url,
            container_name=container_name,
            credential=credential,
        )

    def __repr__(self) -> str:
        return (
            f"AzureBlobLoader("
            f"account_url={self._account_url!r}, "
            f"container_name={self._container_name!r})"
        )

    def _list_keys(self) -> list[str]:
        kwargs: dict[str, Any] = {}
        if self._prefix is not None:
            kwargs["name_starts_with"] = self._prefix
        return [blob.name for blob in self._container_client.list_blobs(**kwargs)]

    def _fetch_bytes(self, key: str) -> bytes:
        blob_client = self._container_client.get_blob_client(key)
        return blob_client.download_blob().readall()

    def _source(self, key: str) -> str:
        return f"{self._account_url}/{self._container_name}/{key}"

    def _metadata(self, key: str) -> dict[str, str]:
        return {
            "account_url": self._account_url,
            "container": self._container_name,
            "blob_name": key,
        }
