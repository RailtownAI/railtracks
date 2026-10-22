from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from ..metric import DistanceMetric


def _unit(vector: list[float]) -> np.ndarray:
    values = np.asarray(vector, dtype=np.float32)
    if values.ndim != 1 or values.size == 0 or not np.isfinite(values).all():
        raise ValueError(
            "Turbovec vectors must be non-empty finite one-dimensional values"
        )
    norm = float(np.linalg.norm(values))
    if not math.isfinite(norm):
        raise ValueError("Turbovec vector norm must be finite")
    if norm == 0.0:
        return np.zeros_like(values)
    return np.ascontiguousarray(values / norm, dtype=np.float32)


def _matches(payload: dict[str, Any], filters: dict[str, Any]) -> bool:
    return all(payload.get(key) == value for key, value in filters.items())


class TurbovecBackend:
    """Local TurboQuant vector backend with a JSON metadata sidecar.

    Vectors are normalized before indexing and searching, so inner-product scores
    have cosine semantics. The first upsert batch should be representative if a
    caller chooses to calibrate the underlying index separately.
    """

    def __init__(
        self,
        snapshot_path: str | Path | None = None,
        *,
        metric: DistanceMetric = DistanceMetric.COSINE,
        bit_width: int = 4,
    ) -> None:
        if metric is not DistanceMetric.COSINE:
            raise ValueError("TurbovecBackend supports cosine similarity only")
        if bit_width not in (2, 3, 4):
            raise ValueError("Turbovec bit_width must be 2, 3, or 4")
        self._snapshot_path = Path(snapshot_path) if snapshot_path is not None else None
        self._bit_width = bit_width
        self._lock = asyncio.Lock()
        self._index: Any = None
        self._payloads: dict[str, dict[str, Any]] = {}
        self._id_to_uint: dict[str, int] = {}
        self._uint_to_id: dict[int, str] = {}
        if self._snapshot_path is not None and self._snapshot_path.exists():
            self._load_snapshot()

    def _load_snapshot(self) -> None:
        manifest = json.loads(self._snapshot_path.read_text(encoding="utf-8"))
        index_name, payload_name = manifest["index"], manifest["payloads"]
        if (
            not isinstance(index_name, str)
            or Path(index_name).name != index_name
            or not index_name.endswith(".tvim")
            or not isinstance(payload_name, str)
            or Path(payload_name).name != payload_name
            or not payload_name.endswith(".payloads.json")
        ):
            raise ValueError("invalid Turbovec snapshot manifest")
        index_path = self._snapshot_path.parent / index_name
        payload_path = self._snapshot_path.parent / payload_name
        try:
            from turbovec import IdMapIndex
        except ImportError:
            raise ImportError(
                "turbovec is required for TurbovecBackend. Install railtracks[stores-turbovec]."
            ) from None
        self._index = IdMapIndex.load(str(index_path))
        data = json.loads(payload_path.read_text(encoding="utf-8"))
        self._payloads = data["payloads"]
        self._id_to_uint = {key: int(value) for key, value in data["ids"].items()}
        self._uint_to_id = {value: key for key, value in self._id_to_uint.items()}
        if (
            len(self._uint_to_id) != len(self._id_to_uint)
            or any(value < 0 or value >= 1 << 64 for value in self._id_to_uint.values())
            or len(self._payloads) != len(self._index)
            or any(
                key not in self._id_to_uint
                or not self._index.__contains__(self._id_to_uint[key])
                for key in self._payloads
            )
        ):
            raise ValueError("inconsistent Turbovec snapshot index and payloads")

    def _stable_id(self, id_: str) -> int:
        current = self._id_to_uint.get(id_)
        if current is not None:
            return current
        candidate = int.from_bytes(
            hashlib.blake2b(id_.encode(), digest_size=8).digest(), "big"
        )
        while candidate in self._uint_to_id and self._uint_to_id[candidate] != id_:
            candidate = (candidate + 1) & ((1 << 64) - 1)
        self._id_to_uint[id_] = candidate
        self._uint_to_id[candidate] = id_
        return candidate

    async def _ready(self, dim: int | None = None) -> Any:
        if self._index is not None:
            if (
                dim is not None
                and self._index.dim is not None
                and self._index.dim != dim
            ):
                raise ValueError(
                    f"vector dimension changed from {self._index.dim} to {dim}"
                )
            return self._index
        try:
            from turbovec import IdMapIndex
        except ImportError:
            raise ImportError(
                "turbovec is required for TurbovecBackend. Install railtracks[stores-turbovec]."
            ) from None
        self._index = await asyncio.to_thread(
            IdMapIndex, dim=dim, bit_width=self._bit_width
        )
        return self._index

    async def upsert(self, id: str, vector: list[float], payload: dict) -> None:
        normalized = _unit(vector)
        value = (
            json.loads(json.dumps(payload, ensure_ascii=False, allow_nan=False))
            if self._snapshot_path is not None
            else dict(payload)
        )
        async with self._lock:
            index = await self._ready(int(normalized.size))
            uid = self._stable_id(id)
            await asyncio.to_thread(index.remove, uid)
            await asyncio.to_thread(
                index.add_with_ids,
                normalized.reshape(1, -1),
                np.asarray([uid], dtype=np.uint64),
            )
            self._payloads[id] = value
            await self._flush()

    async def search(
        self, vector: list[float], top_k: int, filters: dict
    ) -> list[tuple[str, float, dict]]:
        if top_k <= 0:
            return []
        normalized = _unit(vector)
        async with self._lock:
            if self._index is None or len(self._index) == 0:
                return []
            allowed = [
                self._id_to_uint[key]
                for key, payload in self._payloads.items()
                if _matches(payload, filters)
            ]
            if not allowed:
                return []
            scores, ids = await asyncio.to_thread(
                self._index.search,
                normalized.reshape(1, -1),
                min(top_k, len(allowed)),
                allowlist=np.asarray(allowed, dtype=np.uint64),
            )
            return [
                (
                    self._uint_to_id[int(uid)],
                    float(score),
                    dict(self._payloads[self._uint_to_id[int(uid)]]),
                )
                for score, uid in zip(scores[0], ids[0])
                if int(uid) in self._uint_to_id
                and self._uint_to_id[int(uid)] in self._payloads
            ]

    async def delete(self, id: str) -> None:
        async with self._lock:
            uid = self._id_to_uint.get(id)
            if uid is not None and self._index is not None:
                await asyncio.to_thread(self._index.remove, uid)
            self._payloads.pop(id, None)
            await self._flush()

    async def delete_where(self, filters: dict) -> None:
        async with self._lock:
            removals = [
                key
                for key, payload in self._payloads.items()
                if _matches(payload, filters)
            ]
            if self._index is not None:
                for key in removals:
                    await asyncio.to_thread(self._index.remove, self._id_to_uint[key])
            for key in removals:
                self._payloads.pop(key, None)
            await self._flush()

    async def list_where(self, filters: dict, limit: int) -> list[tuple[str, dict]]:
        if limit <= 0:
            return []
        async with self._lock:
            return [
                (key, dict(value))
                for key, value in self._payloads.items()
                if _matches(value, filters)
            ][:limit]

    async def count(self, filters: dict) -> int:
        async with self._lock:
            return sum(
                _matches(payload, filters) for payload in self._payloads.values()
            )

    async def _flush(self) -> None:
        if self._snapshot_path is None:
            return
        self._snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        if self._index is None:
            return
        previous = {}
        if self._snapshot_path.is_file():
            try:
                previous = json.loads(self._snapshot_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                previous = {}
        generation = hashlib.sha256(os.urandom(32)).hexdigest()
        index_name = f"{self._snapshot_path.name}.{generation}.tvim"
        payload_name = f"{self._snapshot_path.name}.{generation}.payloads.json"
        index_path = self._snapshot_path.parent / index_name
        payload_path = self._snapshot_path.parent / payload_name
        payload_tmp = None
        try:
            await asyncio.to_thread(self._index.write, str(index_path), durable=True)
            content = json.dumps(
                {"ids": self._id_to_uint, "payloads": self._payloads},
                ensure_ascii=False,
                allow_nan=False,
            )
            fd, payload_tmp = tempfile.mkstemp(
                dir=self._snapshot_path.parent, prefix=f".{payload_name}."
            )
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(payload_tmp, payload_path)
            payload_tmp = None
            manifest = json.dumps({"index": index_name, "payloads": payload_name})
            fd, manifest_tmp = tempfile.mkstemp(
                dir=self._snapshot_path.parent, prefix=f".{self._snapshot_path.name}."
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    stream.write(manifest)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(manifest_tmp, self._snapshot_path)
                directory_fd = os.open(self._snapshot_path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
                for old_name in (previous.get("index"), previous.get("payloads")):
                    if isinstance(old_name, str) and Path(old_name).name == old_name:
                        old_path = self._snapshot_path.parent / old_name
                        if old_path not in (index_path, payload_path):
                            old_path.unlink(missing_ok=True)
            finally:
                if os.path.exists(manifest_tmp):
                    os.unlink(manifest_tmp)
        finally:
            if payload_tmp is not None and os.path.exists(payload_tmp):
                os.unlink(payload_tmp)
