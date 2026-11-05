"""Sanitizing wrapper around any :class:`BaseDocumentLoader`.

Teams that need to redact PII, normalize encodings, or strip secrets
before content reaches the embedder construct their own ``Sanitizer``
and wrap their existing loader::

    class MyRedactor:
        def sanitize(self, document: Document) -> Document: ...


    loader = SanitizingLoader(TextLoader(...), MyRedactor())

``sanitize`` may be synchronous or async — if it returns a coroutine
the loader awaits it. Use the async form for I/O-heavy redaction
(remote DLP services, vector classifiers); use sync for pure regex /
string work. No PII logic is baked into the framework.

If ``sanitize`` raises, that document is dropped and yielded as a
``LoadFailure`` instead, so unsanitized content never reaches the
embedder and the remaining documents still load.
"""

from __future__ import annotations

import inspect
from collections.abc import AsyncGenerator, Awaitable
from typing import Protocol, Union, runtime_checkable

from ..models import Document
from .base import BaseDocumentLoader
from .models import LoadFailure


@runtime_checkable
class Sanitizer(Protocol):
    """Structural protocol for sanitizing a single document.

    Implementations may modify and return the input, or return a fresh
    ``Document``. ``sanitize`` may be synchronous or asynchronous (the
    return type may be a ``Document`` or an ``Awaitable[Document]``).
    An error raised here drops that document: ``SanitizingLoader`` yields
    it as a ``LoadFailure``, which ``RetrievalRuntime`` reports as a
    ``DocumentFailed`` and ``load()``/``aload()`` raise.
    """

    def sanitize(self, document: Document) -> Union[Document, Awaitable[Document]]: ...


class SanitizingLoader(BaseDocumentLoader):
    """Wraps an inner loader and runs every yielded document through a
    caller-supplied ``Sanitizer``. ``LoadFailure`` items from the inner
    loader are passed through unchanged, and a document whose sanitizer
    raises is yielded as a ``LoadFailure`` in its place."""

    def __init__(self, inner: BaseDocumentLoader, sanitizer: Sanitizer) -> None:
        self._inner = inner
        self._sanitizer = sanitizer

    async def astream(self) -> AsyncGenerator[Document | LoadFailure, None]:
        async for doc in self._inner.astream():
            if isinstance(doc, LoadFailure):
                yield doc
                continue
            try:
                result = self._sanitizer.sanitize(doc)
                if inspect.isawaitable(result):
                    result = await result
            except Exception as exc:
                source = doc.source if doc.source is not None else str(doc.id)
                yield LoadFailure(source=source, error=exc)
                continue
            yield result
