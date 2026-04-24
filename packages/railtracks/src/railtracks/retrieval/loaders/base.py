from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from railtracks.retrieval.models import Document


class BaseDocumentLoader(ABC):
    """Base class for all document loaders.

    Subclass this to integrate any new document source. Only `load()`
    must be implemented. `aload()` and `astream()` have default
    implementations but can be overridden for true async or streaming I/O.

    `RAGPipeline` always consumes `astream()` internally so documents
    flow into the chunker as they become ready rather than waiting for
    the full corpus to load. Loaders backed by cloud OCR or other slow
    per-document I/O should override `astream()` to yield documents
    concurrently.
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

    async def astream(self) -> AsyncIterator[Document]:
        """Streams Documents one at a time as they become ready.

        The default implementation materialises `aload()` and yields
        from the result. Override this in loaders that can produce
        documents incrementally (e.g. cloud OCR, paginated APIs) to
        avoid holding the full corpus in memory.

        Yields:
            Individual `Document` objects.
        """
        for doc in await self.aload():
            yield doc
