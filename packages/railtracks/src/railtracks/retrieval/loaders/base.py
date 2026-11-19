from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import aclosing

from railtracks.retrieval.loaders.models import LoadFailure
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

    A source that cannot be read (an undecodable file, a corrupt PDF, a
    failed download) is yielded as a `LoadFailure` instead of raising, so
    the rest of the corpus still loads. Subclasses wrap each source's
    documents in `_isolate_source()` to get this behaviour. Errors in the
    loader's own configuration, such as a missing root path, still raise.
    """

    @abstractmethod
    async def astream(self) -> AsyncGenerator[Document | LoadFailure, None]:
        """Stream documents one at a time as they become ready.

        The single primitive from which `load()` and `aload()` are
        derived. Documents must be yielded individually as soon as they
        are available — implementations must not buffer the full corpus
        before yielding.

        Yields:
            Document | LoadFailure: The next available document, or a
            `LoadFailure` for a source that could not be read.
        """
        yield  # type: ignore This needs to be here to make this an async generator, read: https://discuss.python.org/t/overloads-of-async-generators-inconsistent-coroutine-wrapping/56665

    async def aload(self) -> list[Document]:
        """Load all documents and return them as a list.

        Collects all documents from `astream()` into memory. Prefer
        `astream()` for large corpora to avoid holding the full corpus
        in memory.

        Returns:
            list[Document]: All documents produced by this loader.

        Raises:
            Exception: The error of the first `LoadFailure` from `astream()`.
                Use `astream()` to skip unreadable sources instead.
        """
        documents: list[Document] = []
        async with aclosing(self.astream()) as stream:
            async for item in stream:
                if isinstance(item, LoadFailure):
                    raise item.error
                documents.append(item)
        return documents

    def load(self) -> list[Document]:
        """Load all documents synchronously and return them as a list.

        Blocking wrapper around `aload()`. Safe to call from anywhere:

        - **No event loop running** (plain scripts): runs `aload()` directly
          via `asyncio.run()`.
        - **Event loop already running** (Jupyter, FastAPI handlers, other
          coroutines): runs `aload()` on a temporary worker thread with its
          own event loop, blocking the caller until results are ready.

        Prefer `astream()` or `aload()` directly wherever async I/O is
        available — this method only exists for sync convenience.

        Returns:
            list[Document]: All documents produced by this loader.

        Raises:
            Exception: The error of the first `LoadFailure` from `astream()`.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # No loop in this thread — safe to spin one up.
            return asyncio.run(self.aload())

        # A loop is already running. Run aload() on a worker thread that
        # creates its own event loop. Avoids "asyncio.run() cannot be called
        # from a running event loop" in Jupyter / async contexts.
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, self.aload()).result()

    @staticmethod
    async def _isolate_source(
        source: str, documents: AsyncIterator[Document]
    ) -> AsyncGenerator[Document | LoadFailure, None]:
        """Yield one source's documents, ending in a `LoadFailure` if it fails.

        Documents yielded before the error are passed through unchanged; the
        error then becomes a single `LoadFailure` and the rest of that source
        is skipped, leaving the caller free to move on to the next source.

        Args:
            source: Identifier reported on the `LoadFailure`.
            documents: The documents produced by reading that one source.

        Yields:
            Document | LoadFailure: The source's documents, then a
            `LoadFailure` if reading it raised.
        """
        try:
            async for doc in documents:
                yield doc
        except Exception as exc:
            yield LoadFailure(source=source, error=exc)
