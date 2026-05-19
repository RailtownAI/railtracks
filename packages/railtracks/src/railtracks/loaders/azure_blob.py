from __future__ import annotations

from typing import Any, Optional

from railtracks.vector_stores.chunking.base_chunker import Chunk

from .base import BaseStorageLoader


class AzureBlobLoader(BaseStorageLoader):
    """Document loader for Azure Blob Storage.

    Fetches blobs from a container and returns them as
    :class:`~railtracks.vector_stores.chunking.base_chunker.Chunk` objects
    with UTF-8 decoded content and source metadata.

    Authentication defaults to ``DefaultAzureCredential``, which resolves
    credentials from environment variables, managed identity, the Azure CLI,
    and other standard sources automatically. Pass an explicit ``credential``
    to override.

    Requires the ``azure-blob`` extra: ``pip install railtracks[azure-blob]``.

    Args:
        account_url: Azure Storage account URL, e.g.
            ``"https://<account>.blob.core.windows.net"``.
        container_name: Name of the blob container.
        credential: Azure credential used for authentication. Accepts any
            ``azure.core.credentials.TokenCredential``,
            ``azure.core.credentials.AzureSasCredential``, or an account key
            string. Defaults to ``DefaultAzureCredential()`` when ``None``.
        encoding: Text encoding used to decode blob bytes. Defaults to ``"utf-8"``.

    Raises:
        ImportError: If ``azure-storage-blob`` or ``azure-identity`` are not installed.

    Example::

        # Default credential (env vars, managed identity, Azure CLI …)
        loader = AzureBlobLoader(
            "https://myaccount.blob.core.windows.net",
            "my-container",
        )
        chunks = loader.load(prefix="reports/")

        # Explicit SAS token
        from azure.core.credentials import AzureSasCredential
        loader = AzureBlobLoader(
            "https://myaccount.blob.core.windows.net",
            "my-container",
            credential=AzureSasCredential("<sas-token>"),
        )

        # Load specific blobs
        chunks = loader.load_keys(["readme.txt", "data/report.txt"])

        # Async usage
        chunks = await loader.aload(prefix="reports/")
    """

    def __init__(
        self,
        account_url: str,
        container_name: str,
        *,
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

        if credential is None:
            try:
                from azure.identity import DefaultAzureCredential

                credential = DefaultAzureCredential()
            except ImportError:
                raise ImportError(
                    "azure-identity is required for default credential resolution. "
                    "Install it via `pip install railtracks[azure-blob]` or `uv add railtracks[azure-blob]`."
                )

        self._account_url = account_url.rstrip("/")
        self._container_name = container_name
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

    def load(self, prefix: Optional[str] = None) -> list[Chunk]:
        """Load all blobs from the container, optionally filtered by prefix.

        Args:
            prefix: Optional blob name prefix. Only blobs whose names start
                with this string are loaded.

        Returns:
            list[Chunk]: All matching blobs as Chunk objects.
        """
        list_kwargs: dict[str, Any] = {}
        if prefix is not None:
            list_kwargs["name_starts_with"] = prefix

        blob_names = [
            blob.name
            for blob in self._container_client.list_blobs(**list_kwargs)
        ]
        return self.load_keys(blob_names)

    def load_keys(self, keys: list[str]) -> list[Chunk]:
        """Load specific blobs by name.

        Args:
            keys: List of blob names to load.

        Returns:
            list[Chunk]: Specified blobs as Chunk objects.
        """
        chunks: list[Chunk] = []
        for blob_name in keys:
            blob_client = self._container_client.get_blob_client(blob_name)
            data = blob_client.download_blob().readall()
            content = data.decode(self._encoding)
            chunks.append(
                Chunk(
                    content=content,
                    document=blob_name,
                    metadata={
                        "source": f"{self._account_url}/{self._container_name}/{blob_name}",
                        "account_url": self._account_url,
                        "container": self._container_name,
                        "blob_name": blob_name,
                    },
                )
            )
        return chunks
