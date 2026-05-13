"""Tests for retrieval/stores/protocol.py — Store protocol checks."""

from __future__ import annotations

from uuid import UUID

from railtracks.retrieval.stores.models import (
    RetrievedStoreEntry,
    StoreEntry,
    StoreQuery,
    StoreScope,
)
from railtracks.retrieval.stores.protocol import Store


class _CompleteStore:
    async def write(self, entry: StoreEntry) -> str:
        return str(entry.id)

    async def read(self, query: StoreQuery) -> list[RetrievedStoreEntry]:
        return []

    async def delete(self, id: UUID) -> None:
        pass

    async def clear(self, scope: StoreScope) -> None:
        pass


class _IncompleteStore:
    async def write(self, entry: StoreEntry) -> str:
        return str(entry.id)

    async def read(self, query: StoreQuery) -> list[RetrievedStoreEntry]:
        return []

    # missing delete and clear


def test_complete_implementation_satisfies_store():
    obj = _CompleteStore()
    assert isinstance(obj, Store)


def test_incomplete_implementation_fails_store():
    obj = _IncompleteStore()
    assert not isinstance(obj, Store)
