from __future__ import annotations

import asyncio
import uuid
from abc import ABC, abstractmethod
from typing import Callable, Optional

from railtracks.vector_stores.chunking.base_chunker import Chunk


class BaseStorageWriter(ABC):
    """Abstract base class for remote cloud storage writers.

    Subclasses persist content (raw strings or :class:`Chunk` objects) to a
    specific cloud provider and return the URIs or keys of the objects written.
    """

    @abstractmethod
    def write(self, chunks: list[Chunk], prefix: Optional[str] = None) -> list[str]:
        """Write chunks to storage.

        Args:
            chunks: Chunk objects to persist.
            prefix: Optional prefix prepended to auto-derived object keys.
                    Ignored by providers where it has no meaning (e.g. SQL).

        Returns:
            list[str]: URIs or keys of the objects written, one per chunk.
        """

    @abstractmethod
    def write_key(self, key: str, content: str) -> str:
        """Write raw text content at an explicit key.

        Args:
            key: The storage key, path, or ID (relative to bucket/container/table).
            content: Text content to write.

        Returns:
            str: The full URI or key of the written object.
        """

    async def awrite(
        self, chunks: list[Chunk], prefix: Optional[str] = None
    ) -> list[str]:
        """Async wrapper around :meth:`write`."""
        return await asyncio.to_thread(self.write, chunks, prefix)

    async def awrite_key(self, key: str, content: str) -> str:
        """Async wrapper around :meth:`write_key`."""
        return await asyncio.to_thread(self.write_key, key, content)

    # ------------------------------------------------------------------
    # Protected helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _derive_key(
        chunk: Chunk,
        prefix: Optional[str],
        key_fn: Optional[Callable[[Chunk], str]],
    ) -> str:
        """Determine the storage key for a chunk.

        Priority order:
        1. ``key_fn(chunk)`` when provided.
        2. ``chunk.id`` when set.
        3. ``chunk.document`` when set.
        4. A freshly generated UUID4 string as a last resort.

        The ``prefix`` is prepended to whatever key is derived.
        """
        if key_fn is not None:
            raw = key_fn(chunk)
        elif chunk.id:
            raw = chunk.id
        elif chunk.document:
            raw = chunk.document
        else:
            raw = str(uuid.uuid4())

        return f"{prefix}{raw}" if prefix else raw
