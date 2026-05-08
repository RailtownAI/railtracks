from __future__ import annotations

import asyncio
import json
from pathlib import Path

import numpy as np

from ..metric import DistanceMetric


class InMemoryBackend:
    """Reference VectorBackend using numpy.

    Thread-safe via asyncio.Lock. When snapshot_path is provided the state is
    loaded from that file on construction and flushed back to it after every
    mutating operation (upsert, delete, delete_where), giving lightweight
    persistence without any external dependencies.
    """

    def __init__(
        self,
        snapshot_path: str | Path | None = None,
        *,
        metric: DistanceMetric = DistanceMetric.COSINE,
    ) -> None:
        self._vectors: dict[str, list[float]] = {}
        self._payloads: dict[str, dict] = {}
        self._lock = asyncio.Lock()
        self._metric = metric
        self._snapshot_path = Path(snapshot_path) if snapshot_path is not None else None

        if self._snapshot_path is not None and self._snapshot_path.exists():
            data = json.loads(self._snapshot_path.read_text())
            self._vectors = data.get("vectors", {})
            self._payloads = data.get("payloads", {})

    async def upsert(self, id: str, vector: list[float], payload: dict) -> None:
        async with self._lock:
            self._vectors[id] = vector
            self._payloads[id] = payload
            self._flush()

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
            stored = np.array(
                [self._vectors[c] for c in candidates], dtype=np.float64
            )

            if self._metric is DistanceMetric.COSINE:
                q_norm = np.linalg.norm(query_vec)
                if q_norm == 0:
                    return [(c, 0.0, dict(self._payloads[c])) for c in candidates[:top_k]]
                norms = np.linalg.norm(stored, axis=1)
                norms[norms == 0] = 1.0
                scores = (stored @ query_vec) / (norms * q_norm)

            elif self._metric is DistanceMetric.L2:
                distances = np.linalg.norm(stored - query_vec, axis=1)
                scores = 1.0 / (1.0 + distances)

            else:  # IP
                scores = stored @ query_vec

            top_indices = np.argsort(scores)[::-1][:top_k]
            return [
                (candidates[i], float(scores[i]), dict(self._payloads[candidates[i]]))
                for i in top_indices
            ]

    async def delete(self, id: str) -> None:
        async with self._lock:
            self._vectors.pop(id, None)
            self._payloads.pop(id, None)
            self._flush()

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
            self._flush()

    def _flush(self) -> None:
        """Write current state to snapshot_path. Must be called while holding _lock."""
        if self._snapshot_path is None:
            return
        self._snapshot_path.write_text(
            json.dumps({"vectors": self._vectors, "payloads": self._payloads})
        )


def _matches_filters(payload: dict, filters: dict) -> bool:
    return all(payload.get(k) == v for k, v in filters.items())
