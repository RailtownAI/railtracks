from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any, Optional

from railtracks.retrieval.loaders._pdf_options import (
    BreakdownStrategy,
    validate_breakdown_strategy,
)
from railtracks.retrieval.loaders.base import BaseDocumentLoader
from railtracks.retrieval.loaders.cloud._common import stream_object_documents
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
    instances with source metadata. Listing is recursive — any blob
    whose name starts with ``prefix`` is loaded,
    including subfolders.

    Text objects are decoded with ``encoding``. PDFs are parsed with the same
    logic as ``PyPDFLoader`` (requires the ``pdf`` extra), split according to
    ``pdf_breakdown_strategy``. Any other object that is not valid text is
    skipped with a warning.

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

        self._account_url = account_url.rstrip("/")
        self._container_name = container_name
        self._prefix = prefix
        self._keys = list(keys) if keys is not None else None
        self._encoding = encoding
        validate_breakdown_strategy(
            pdf_breakdown_strategy, name="pdf_breakdown_strategy"
        )
        self._pdf_breakdown_strategy = pdf_breakdown_strategy
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

    def _fetch_bytes(self, blob_name: str) -> bytes:
        blob_client = self._container_client.get_blob_client(blob_name)
        return blob_client.download_blob().readall()

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
            data = await asyncio.to_thread(self._fetch_bytes, name)
            async for doc in stream_object_documents(
                data,
                key=name,
                source=f"{self._account_url}/{self._container_name}/{name}",
                metadata={
                    "account_url": self._account_url,
                    "container": self._container_name,
                    "blob_name": name,
                },
                encoding=self._encoding,
                pdf_breakdown_strategy=self._pdf_breakdown_strategy,
            ):
                yield doc
