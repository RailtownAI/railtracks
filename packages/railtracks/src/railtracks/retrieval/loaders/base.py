from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator

from railtracks.retrieval.models import Document


class BaseDocumentLoader(ABC):
    """Abstract base class for all document loaders.

    Defines the streaming interface for loading documents from any source.
    Subclasses must implement `astream()`, which is the single primitive
    from which all other methods are derived.

    The pipeline always consumes `astream()` internally, allowing documents
    to flow into the chunker as they become ready rather than waiting for the
    full corpus to load. This enables true streaming behaviour where a document
    is chunked and embedded while subsequent documents are still being loaded.

    """

    @abstractmethod
    async def astream(self) -> AsyncGenerator[Document, None]:
        """Stream documents one at a time as they become ready.

        The single primitive from which `load()` and `aload()` are
        derived. Documents must be yielded individually as soon as they
        are available — implementations must not buffer the full corpus
        before yielding.

        Yields:
            Document: The next available document from the source.
        """
        yield  # type: ignore This needs to be here to make this an async generator, read: https://discuss.python.org/t/overloads-of-async-generators-inconsistent-coroutine-wrapping/56665

    async def aload(self) -> list[Document]:
        """Load all documents and return them as a list.

        Collects all documents from `astream()` into memory. Prefer
        `astream()` for large corpora to avoid holding the full corpus
        in memory.

        Returns:
            list[Document]: All documents produced by this loader.
        """
        return [doc async for doc in self.astream()]

    def load(self) -> list[Document]:
        """Load all documents synchronously and return them as a list.

        Blocking wrapper around `aload()` for use outside of an async
        context. Prefer `astream()` or `aload()` wherever async I/O
        is available.

        Returns:
            list[Document]: All documents produced by this loader.
        """
        return asyncio.run(self.aload())
