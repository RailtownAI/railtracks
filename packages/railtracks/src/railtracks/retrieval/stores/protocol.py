from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .models import RetrievedStoreEntry, StoreEntry, StoreQuery, StoreScope


@runtime_checkable
class Store(Protocol):
    async def write(self, entry: StoreEntry) -> str: ...
    async def read(self, query: StoreQuery) -> list[RetrievedStoreEntry]: ...
    async def delete(self, id: str) -> None: ...
    async def clear(self, scope: StoreScope) -> None: ...
    async def delete_where(
        self,
        filters: dict[str, Any] | None = None,
        *,
        metadata_filters: dict[str, Any] | None = None,
    ) -> None: ...
    async def find(
        self,
        filters: dict[str, Any] | None = None,
        limit: int = 1,
        *,
        metadata_filters: dict[str, Any] | None = None,
    ) -> list[StoreEntry]: ...
    async def count(
        self,
        filters: dict[str, Any] | None = None,
        *,
        metadata_filters: dict[str, Any] | None = None,
    ) -> int: ...
