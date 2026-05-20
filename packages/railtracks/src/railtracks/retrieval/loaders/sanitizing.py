"""Sanitizing wrapper around any :class:`BaseDocumentLoader`.

Teams that need to redact PII, normalize encodings, or strip secrets
before content reaches the embedder construct their own ``Sanitizer``
and wrap their existing loader::

    class MyRedactor:
        def sanitize(self, document: Document) -> Document:
            ...

    loader = SanitizingLoader(TextLoader(...), MyRedactor())

``sanitize`` may be synchronous or async — if it returns a coroutine
the loader awaits it. Use the async form for I/O-heavy redaction
(remote DLP services, vector classifiers); use sync for pure regex /
string work. No PII logic is baked into the framework.
"""

from __future__ import annotations

import inspect
from collections.abc import AsyncGenerator, Awaitable
from typing import Protocol, Union, runtime_checkable

from ..models import Document
from .base import BaseDocumentLoader


@runtime_checkable
class Sanitizer(Protocol):
    """Structural protocol for sanitizing a single document.

    Implementations may modify and return the input, or return a fresh
    ``Document``. ``sanitize`` may be synchronous or asynchronous (the
    return type may be a ``Document`` or an ``Awaitable[Document]``).
    Errors raised here propagate; the framework does not swallow them.
    """

    def sanitize(
        self, document: Document
    ) -> Union[Document, Awaitable[Document]]: ...


class SanitizingLoader(BaseDocumentLoader):
    """Wraps an inner loader and runs every yielded document through a
    caller-supplied ``Sanitizer``."""

    def __init__(
        self, inner: BaseDocumentLoader, sanitizer: Sanitizer
    ) -> None:
        self._inner = inner
        self._sanitizer = sanitizer

    async def astream(self) -> AsyncGenerator[Document, None]:
        async for doc in self._inner.astream():
            result = self._sanitizer.sanitize(doc)
            if inspect.isawaitable(result):
                result = await result
            yield result
