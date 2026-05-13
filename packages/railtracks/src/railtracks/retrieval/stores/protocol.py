from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from .models import RetrievedStoreEntry, StoreEntry, StoreQuery, StoreScope


@runtime_checkable
class Store(Protocol):
    async def write(self, entry: StoreEntry) -> str: ...
    async def read(self, query: StoreQuery) -> list[RetrievedStoreEntry]: ...
    async def delete(self, id: UUID) -> None: ...
    async def clear(self, scope: StoreScope) -> None: ...
