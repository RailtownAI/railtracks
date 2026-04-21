from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod

from railtracks.rag.models import Document


class BaseDocumentLoader(ABC):
    """Base class for all document loaders.

    Subclass this to integrate any new document source. Only `load()`
    must be implemented; `aload()` defaults to running `load()` in a
    thread pool and can be overridden for true async I/O.
    """

    @abstractmethod
    def load(self) -> list[Document]:
        """Loads and returns a list of Documents.

        Returns:
            A list of `Document` objects.
        """
        ...

    async def aload(self) -> list[Document]:
        """Async variant of `load()`. Defaults to running `load()` in a thread pool.

        Override this method in subclasses that support native async I/O.

        Returns:
            A list of `Document` objects.
        """
        return await asyncio.to_thread(self.load)
