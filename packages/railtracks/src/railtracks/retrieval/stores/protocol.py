from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from .models import MemoryEntry, MemoryQuery, MemoryScope, RetrievedMemoryEntry


@runtime_checkable
class Store(Protocol):
    async def write(self, entry: MemoryEntry) -> str: ...
    async def read(self, query: MemoryQuery) -> list[RetrievedMemoryEntry]: ...
    async def delete(self, id: UUID) -> None: ...
    async def clear(self, scope: MemoryScope) -> None: ...
