from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any, Optional

from railtracks.retrieval.loaders.base import BaseDocumentLoader
from railtracks.retrieval.loaders.cloud._common import infer_document_type
from railtracks.retrieval.models import Document


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


class AzureBlobLoader(BaseDocumentLoader):
    """Document loader for Azure Blob Storage.

    Fetches blobs from a container and yields them as :class:`Document`
    instances with UTF-8 decoded content and source metadata. Listing is
    recursive — any blob whose name starts with ``prefix`` is loaded,
    including subfolders.

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

    Raises:
        ImportError: If ``azure-storage-blob`` or ``azure-identity`` are not installed.
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
    ) -> None:
        try:
            from azure.storage.blob import ContainerClient
        except ImportError:
            raise ImportError(
                "azure-storage-blob is required for Azure Blob loading. "
                "Install it via `pip install railtracks[azure-blob]` or `uv add railtracks[azure-blob]`."
            )

        credential = _ensure_credential(credential)

        self._account_url = account_url.rstrip("/")
        self._container_name = container_name
        self._prefix = prefix
        self._keys = list(keys) if keys is not None else None
        self._encoding = encoding
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

    def _fetch_document(self, blob_name: str) -> Document:
        blob_client = self._container_client.get_blob_client(blob_name)
        data = blob_client.download_blob().readall()
        content = data.decode(self._encoding)
        return Document(
            content=content,
            type=infer_document_type(blob_name),
            source=f"{self._account_url}/{self._container_name}/{blob_name}",
            metadata={
                "account_url": self._account_url,
                "container": self._container_name,
                "blob_name": blob_name,
            },
        )

    async def astream(self) -> AsyncGenerator[Document, None]:
        """Stream documents one at a time as each blob is downloaded.

        Yields:
            Document: The next loaded document.
        """
        if self._keys is not None:
            names = self._keys
        else:
            names = await asyncio.to_thread(self._list_keys)

        for name in names:
            yield await asyncio.to_thread(self._fetch_document, name)
