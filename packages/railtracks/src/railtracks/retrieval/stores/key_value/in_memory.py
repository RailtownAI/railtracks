from __future__ import annotations

import asyncio
import json
from pathlib import Path


class InMemoryKeyValueStore:
    """Reference :class:`KeyValueStore` backed by an in-process dict.

    Thread-safe via ``asyncio.Lock``. When ``snapshot_path`` is provided the
    state is loaded from that file on construction and flushed back to it after
    every mutating operation (``set``, ``delete``, ``clear``), giving
    lightweight persistence with no external dependencies. This mirrors the
    persistence model of the vector
    :class:`~railtracks.retrieval.stores.vector.backends.in_memory.InMemoryBackend`:
    leave ``snapshot_path`` unset for an ephemeral store, pass a path for a
    persistent one.
    """

    def __init__(self, snapshot_path: str | Path | None = None) -> None:
        self._data: dict[str, str] = {}
        self._lock = asyncio.Lock()
        self._snapshot_path = (
            Path(snapshot_path) if snapshot_path is not None else None
        )

        if self._snapshot_path is not None and self._snapshot_path.exists():
            self._data = json.loads(self._snapshot_path.read_text())

    async def set(self, key: str, value: str) -> None:
        async with self._lock:
            self._data[key] = value
            await self._flush()

    async def get(self, key: str) -> str | None:
        async with self._lock:
            return self._data.get(key)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._data.pop(key, None)
            await self._flush()

    async def keys(self) -> list[str]:
        async with self._lock:
            return list(self._data.keys())

    async def items(self) -> dict[str, str]:
        async with self._lock:
            return dict(self._data)

    async def clear(self) -> None:
        async with self._lock:
            self._data.clear()
            await self._flush()

    async def _flush(self) -> None:
        """Persist current state to ``snapshot_path``. Must hold ``_lock``.

        The JSON encode runs on the event loop (the snapshot is consistent with
        the in-memory state held by the lock); the disk write is offloaded to a
        thread so the event loop is not blocked on I/O.
        """
        if self._snapshot_path is None:
            return
        payload = json.dumps(self._data)
        await asyncio.to_thread(self._snapshot_path.write_text, payload)
