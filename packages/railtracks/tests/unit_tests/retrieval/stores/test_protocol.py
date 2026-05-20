"""Tests for retrieval/stores/protocol.py — Store protocol checks."""

from __future__ import annotations

from typing import Any
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

    async def delete_where(self, filters: dict[str, Any]) -> None:
        pass

    async def find(
        self, filters: dict[str, Any], limit: int = 1
    ) -> list[StoreEntry]:
        return []

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        return 0


class _IncompleteStore:
    async def write(self, entry: StoreEntry) -> str:
        return str(entry.id)

    async def read(self, query: StoreQuery) -> list[RetrievedStoreEntry]:
        return []

    # missing delete, clear, delete_where, find


def test_complete_implementation_satisfies_store():
    obj = _CompleteStore()
    assert isinstance(obj, Store)


def test_incomplete_implementation_fails_store():
    obj = _IncompleteStore()
    assert not isinstance(obj, Store)
