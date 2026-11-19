"""Tests for retrieval/stores/protocol.py — Store protocol checks."""

from __future__ import annotations

from typing import Any

from railtracks.retrieval.stores.models import (
    AllScopes,
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

    async def delete(self, id: str) -> None:
        pass

    async def clear(self, scope: StoreScope) -> None:
        pass

    async def delete_where(
        self,
        filters: dict[str, Any] | None = None,
        *,
        metadata_filters: dict[str, Any] | None = None,
    ) -> None:
        pass

    async def find(
        self,
        filters: dict[str, Any] | None = None,
        limit: int = 1,
        *,
        metadata_filters: dict[str, Any] | None = None,
    ) -> list[StoreEntry]:
        return []

    async def count(
        self,
        filters: dict[str, Any] | None = None,
        *,
        metadata_filters: dict[str, Any] | None = None,
    ) -> int:
        return 0

    async def nearest_neighbors(
        self,
        embedding: list[float],
        k: int,
        scope: StoreScope | AllScopes | None = None,
    ) -> list[RetrievedStoreEntry]:
        return []


class _IncompleteStore:
    async def write(self, entry: StoreEntry) -> str:
        return str(entry.id)

    async def read(self, query: StoreQuery) -> list[RetrievedStoreEntry]:
        return []

    # missing delete, clear, delete_where, find, count, nearest_neighbors


def test_complete_implementation_satisfies_store():
    obj = _CompleteStore()
    assert isinstance(obj, Store)


def test_incomplete_implementation_fails_store():
    obj = _IncompleteStore()
    assert not isinstance(obj, Store)


def test_store_requires_nearest_neighbors():
    without_nearest_neighbors = type(
        "_StoreWithoutNearestNeighbors",
        (),
        {
            name: member
            for name, member in vars(_CompleteStore).items()
            if name != "nearest_neighbors"
        },
    )

    assert not isinstance(without_nearest_neighbors(), Store)
