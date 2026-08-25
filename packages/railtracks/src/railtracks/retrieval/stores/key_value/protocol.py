from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class KeyValueStore(Protocol):
    """Exact-match key-value persistence.

    A deliberately separate contract from the vector
    :class:`~railtracks.retrieval.stores.protocol.Store` protocol. Key-value
    access is exact lookup by key — no similarity search, embeddings, vectors,
    or scope filtering — so it neither does nor should conform to the vector
    ``Store`` protocol. Keeping the two contracts distinct is what stops the
    key-value layer from entangling with the retrieval runtime.

    All methods are ``async`` so a remote backend (Redis, a database) can
    satisfy the same contract without changing callers.
    """

    async def set(self, key: str, value: str) -> None:
        """Store ``value`` under ``key``, overwriting any existing value."""
        ...

    async def get(self, key: str) -> str | None:
        """Return the value stored under ``key``, or ``None`` if absent."""
        ...

    async def delete(self, key: str) -> None:
        """Remove ``key``. A no-op when the key is absent."""
        ...

    async def keys(self) -> list[str]:
        """Return all stored keys."""
        ...

    async def items(self) -> dict[str, str]:
        """Return a snapshot copy of all key-value pairs."""
        ...

    async def clear(self) -> None:
        """Remove every entry."""
        ...
