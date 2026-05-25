from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

from railtracks.retrieval.loaders.base import BaseDocumentLoader
from railtracks.retrieval.models import Document, DocumentType

# asyncio.to_thread can't surface StopIteration across the thread boundary, so we use a sentinel default and stop when next() returns it.
_SENTINEL: object = object()


class LangChainLoaderAdapter(BaseDocumentLoader):
    """Adapts any LangChain ``BaseLoader`` to the railtracks streaming loader API.

    Wraps an object that implements LangChain's loader interface
    (``alazy_load`` / ``lazy_load`` / ``load``) and yields railtracks
    :class:`Document` instances via :meth:`astream`.

    The adapter does not import ``langchain`` itself — it duck-types on the
    wrapped instance, so LangChain stays a fully optional dependency. Install
    whichever LangChain package provides the loader you want
    (``langchain-community``, ``langchain-text-splitters``, etc.) alongside
    railtracks.

    Streaming priority, in order of preference:

    1. ``alazy_load`` — used directly when available. Every modern LangChain
       ``BaseLoader`` provides at least the default implementation, which
       itself streams ``lazy_load`` from a worker thread.
    2. ``lazy_load`` — pulled one item at a time via :func:`asyncio.to_thread`
       so the event loop is not blocked.
    3. ``load`` — eager fallback for legacy loaders that only implement
       ``load``. Materialises the full corpus before yielding.

    Field mapping for each LangChain document:

    - ``page_content`` -> :attr:`Document.content`.
    - ``metadata`` is shallow-copied. If the caller did not pass ``source``,
      ``metadata["source"]`` is popped and used as :attr:`Document.source`.
      Otherwise the explicit ``source`` argument wins and metadata is left
      untouched.
    - :attr:`Document.type` comes from the caller-supplied ``document_type``.

    Args:
        loader: A LangChain ``BaseLoader``-compatible instance.
        document_type: :class:`DocumentType` tag applied to every emitted
            document. Defaults to :attr:`DocumentType.TEXT` because the
            source format depends on the wrapped loader.
        source: Optional override for :attr:`Document.source`. When
            ``None`` (the default), the adapter uses
            ``metadata["source"]`` from each LangChain document if
            present.

    Raises:
        TypeError: If ``loader`` does not expose any of ``alazy_load``,
            ``lazy_load``, or ``load``.

    Example:
        ```python
        from langchain_community.document_loaders import WikipediaLoader
        from railtracks.retrieval.loaders import LangChainLoaderAdapter

        adapter = LangChainLoaderAdapter(
            WikipediaLoader(query="Python (programming language)"),
        )
        async for doc in adapter.astream():
            print(doc.source, len(doc.content))
        ```
    """

    def __init__(
        self,
        loader: Any,
        document_type: DocumentType = DocumentType.TEXT,
        source: str | None = None,
    ) -> None:
        if not any(hasattr(loader, m) for m in ("alazy_load", "lazy_load", "load")):
            raise TypeError(
                "loader must implement the LangChain BaseLoader interface "
                "(expected one of `alazy_load`, `lazy_load`, or `load`)."
            )
        self._loader = loader
        self._document_type = document_type
        self._source = source

    def _convert(self, lc_doc: Any) -> Document:
        content = getattr(lc_doc, "page_content", "")
        metadata = dict(getattr(lc_doc, "metadata", {}) or {})
        if self._source is not None:
            source: str | None = self._source
        else:
            raw_source = metadata.pop("source", None)
            source = str(raw_source) if raw_source is not None else None
        return Document(
            content=content,
            type=self._document_type,
            source=source,
            metadata=metadata,
        )

    async def astream(self) -> AsyncGenerator[Document, None]:
        """Yield converted documents one at a time.

        Yields:
            Document: The next document from the wrapped LangChain loader,
            normalised to the railtracks :class:`Document` model.
        """
        if hasattr(self._loader, "alazy_load"):
            async for lc_doc in self._loader.alazy_load():
                yield self._convert(lc_doc)
            return

        if hasattr(self._loader, "lazy_load"):
            iterator = await asyncio.to_thread(lambda: iter(self._loader.lazy_load()))
            while True:
                lc_doc = await asyncio.to_thread(next, iterator, _SENTINEL)
                if lc_doc is _SENTINEL:
                    return
                yield self._convert(lc_doc)
            return

        docs = await asyncio.to_thread(self._loader.load)
        for lc_doc in docs:
            yield self._convert(lc_doc)
