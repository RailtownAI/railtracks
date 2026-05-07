from __future__ import annotations

import asyncio

import numpy as np


class InMemoryBackend:
    """Reference VectorBackend using numpy for cosine similarity.

    Thread-safe via asyncio.Lock. No persistence across process restarts.
    """

    def __init__(self) -> None:
        self._vectors: dict[str, list[float]] = {}
        self._payloads: dict[str, dict] = {}
        self._lock = asyncio.Lock()

    async def upsert(self, id: str, vector: list[float], payload: dict) -> None:
        async with self._lock:
            self._vectors[id] = vector
            self._payloads[id] = payload

    async def search(
        self, vector: list[float], top_k: int, filters: dict
    ) -> list[tuple[str, float, dict]]:
        async with self._lock:
            candidates = [
                id
                for id, payload in self._payloads.items()
                if _matches_filters(payload, filters)
            ]

            if not candidates:
                return []

            query_vec = np.asarray(vector, dtype=np.float64)
            q_norm = np.linalg.norm(query_vec)
            if q_norm == 0:
                return [(c, 0.0, dict(self._payloads[c])) for c in candidates[:top_k]]

            stored = np.array(
                [self._vectors[c] for c in candidates], dtype=np.float64
            )
            norms = np.linalg.norm(stored, axis=1)
            norms[norms == 0] = 1.0

            scores = (stored @ query_vec) / (norms * q_norm)

            top_indices = np.argsort(scores)[::-1][:top_k]
            return [
                (candidates[i], float(scores[i]), dict(self._payloads[candidates[i]]))
                for i in top_indices
            ]

    async def delete(self, id: str) -> None:
        async with self._lock:
            self._vectors.pop(id, None)
            self._payloads.pop(id, None)

    async def delete_where(self, filters: dict) -> None:
        async with self._lock:
            to_remove = [
                id
                for id, payload in self._payloads.items()
                if _matches_filters(payload, filters)
            ]
            for id in to_remove:
                del self._vectors[id]
                del self._payloads[id]


def _matches_filters(payload: dict, filters: dict) -> bool:
    return all(payload.get(k) == v for k, v in filters.items())
