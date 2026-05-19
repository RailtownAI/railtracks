from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Optional

from railtracks.vector_stores.chunking.base_chunker import Chunk


class BaseStorageLoader(ABC):
    """Abstract base class for remote cloud storage document loaders.

    Subclasses fetch objects from a specific cloud provider and return them
    as :class:`~railtracks.vector_stores.chunking.base_chunker.Chunk` objects
    containing UTF-8 decoded content and provider-specific metadata.
    """

    @abstractmethod
    def load(self, prefix: Optional[str] = None) -> list[Chunk]:
        """Load all documents from the storage container.

        Args:
            prefix: Optional key/path prefix to filter objects.

        Returns:
            list[Chunk]: Documents as Chunk objects with content and metadata.
        """

    @abstractmethod
    def load_keys(self, keys: list[str]) -> list[Chunk]:
        """Load specific documents by key or blob name.

        Args:
            keys: List of object keys or blob names to load.

        Returns:
            list[Chunk]: Documents as Chunk objects with content and metadata.
        """

    async def aload(self, prefix: Optional[str] = None) -> list[Chunk]:
        """Async wrapper around :meth:`load`.

        Args:
            prefix: Optional key/path prefix to filter objects.

        Returns:
            list[Chunk]: Documents as Chunk objects with content and metadata.
        """
        return await asyncio.to_thread(self.load, prefix)

    async def aload_keys(self, keys: list[str]) -> list[Chunk]:
        """Async wrapper around :meth:`load_keys`.

        Args:
            keys: List of object keys or blob names to load.

        Returns:
            list[Chunk]: Documents as Chunk objects with content and metadata.
        """
        return await asyncio.to_thread(self.load_keys, keys)
