from __future__ import annotations

from typing import Any, Callable, Optional

from railtracks.vector_stores.chunking.base_chunker import Chunk

from .base import BaseStorageWriter


class AzureBlobWriter(BaseStorageWriter):
    """Document writer for Azure Blob Storage.

    Uploads text content to a blob container, encoding each blob with the
    configured text encoding and returning the full ``https://`` URI of every
    blob written.  Existing blobs at the same name are overwritten.

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
        encoding: Text encoding used when converting content to bytes. Defaults to ``"utf-8"``.
        content_type: MIME type set on the uploaded blob. Defaults to
            ``"text/plain; charset=utf-8"``.
        key_fn: Optional callable ``(chunk) -> str`` that derives a blob name
            from a :class:`Chunk`. When ``None`` the name falls back to
            ``chunk.id``, then ``chunk.document``, then a random UUID.

    Raises:
        ImportError: If ``azure-storage-blob`` or ``azure-identity`` are not installed.

    Example::

        writer = AzureBlobWriter(
            "https://myaccount.blob.core.windows.net",
            "my-container",
        )

        # Write a list of Chunk objects
        uris = writer.write(chunks, prefix="generated/")

        # Write raw text at an explicit blob name
        uri = writer.write_key("reports/summary.txt", "Today's summary ...")

        # Async usage
        uris = await writer.awrite(chunks, prefix="generated/")
    """

    def __init__(
        self,
        account_url: str,
        container_name: str,
        *,
        credential: Optional[Any] = None,
        encoding: str = "utf-8",
        content_type: str = "text/plain; charset=utf-8",
        key_fn: Optional[Callable[[Chunk], str]] = None,
    ) -> None:
        try:
            from azure.storage.blob import ContainerClient
        except ImportError:
            raise ImportError(
                "azure-storage-blob is required for Azure Blob writing. "
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
        self._content_type = content_type
        self._key_fn = key_fn

        self._container_client = ContainerClient(
            account_url=self._account_url,
            container_name=container_name,
            credential=credential,
        )

    def __repr__(self) -> str:
        return (
            f"AzureBlobWriter("
            f"account_url={self._account_url!r}, "
            f"container_name={self._container_name!r})"
        )

    def write(self, chunks: list[Chunk], prefix: Optional[str] = None) -> list[str]:
        """Write chunks to Azure Blob Storage, one blob per chunk.

        Args:
            chunks: Chunk objects to persist.
            prefix: Optional blob name prefix prepended to each derived name.

        Returns:
            list[str]: Full ``https://`` URIs of every blob written.
        """
        uris: list[str] = []
        for chunk in chunks:
            name = self._derive_key(chunk, prefix, self._key_fn)
            uri = self.write_key(name, chunk.content)
            uris.append(uri)
        return uris

    def write_key(self, key: str, content: str) -> str:
        """Write raw text to Azure Blob Storage at an explicit blob name.

        Args:
            key: Blob name (path within the container).
            content: Text content to upload.

        Returns:
            str: Full ``https://`` URI of the written blob.
        """
        blob_client = self._container_client.get_blob_client(key)
        blob_client.upload_blob(
            content.encode(self._encoding),
            overwrite=True,
            content_settings=self._make_content_settings(),
        )
        return f"{self._account_url}/{self._container_name}/{key}"

    def _make_content_settings(self):
        try:
            from azure.storage.blob import ContentSettings

            return ContentSettings(content_type=self._content_type)
        except ImportError:
            return None
