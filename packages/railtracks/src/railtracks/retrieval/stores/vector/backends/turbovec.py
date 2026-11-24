from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import secrets
import tempfile
import time
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any, TypeVar

import numpy as np

from ..metric import DistanceMetric

_T = TypeVar("_T")


def _unit(vector: list[float]) -> np.ndarray:
    values = np.asarray(vector, dtype=np.float64)
    if values.ndim != 1 or values.size == 0 or not np.isfinite(values).all():
        raise ValueError(
            "Turbovec vectors must be non-empty finite one-dimensional values"
        )
    scale = float(np.max(np.abs(values)))
    if scale == 0.0:
        return np.zeros(values.shape, dtype=np.float32)
    scaled = values / scale
    norm = float(np.linalg.norm(scaled))
    if not math.isfinite(norm):
        raise ValueError("Turbovec vector norm must be finite")
    return np.ascontiguousarray(scaled / norm, dtype=np.float32)


def _matches(payload: dict[str, Any], filters: dict[str, Any]) -> bool:
    return all(payload.get(key) == value for key, value in filters.items())


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    directory_fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _import_id_map_index() -> Any:
    try:
        from turbovec import IdMapIndex
    except ImportError:
        raise ImportError(
            "turbovec is required for TurbovecBackend. Install railtracks[stores-turbovec]."
        ) from None
    return IdMapIndex


def _read_snapshot_manifest(snapshot_path: Path) -> dict[str, Any]:
    if not snapshot_path.is_file():
        return {}
    try:
        manifest = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return manifest if isinstance(manifest, dict) else {}


def _write_fsynced_file(path: Path, content: str, prefix: str) -> None:
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=prefix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(5):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.01 * (attempt + 1))
    except BaseException:
        with suppress(OSError):
            os.unlink(temporary)
        raise


def _owned_generation_path(
    snapshot_path: Path, file_name: object, suffix: str
) -> Path | None:
    if not isinstance(file_name, str) or not file_name.endswith(suffix):
        return None
    prefix = f"{snapshot_path.name}."
    if not file_name.startswith(prefix):
        return None
    generation = file_name[len(prefix) : -len(suffix)]
    if len(generation) != 32 or any(
        character not in "0123456789abcdef" for character in generation
    ):
        return None
    return snapshot_path.parent / file_name


def _remove_previous_snapshot_files(
    snapshot_path: Path,
    previous: dict[str, Any],
    current_paths: tuple[Path, Path],
) -> None:
    for old_name, suffix in (
        (previous.get("index"), ".tvim"),
        (previous.get("payloads"), ".payloads.json"),
    ):
        old_path = _owned_generation_path(snapshot_path, old_name, suffix)
        if old_path is None:
            continue
        if old_path not in current_paths:
            with suppress(OSError):
                old_path.unlink(missing_ok=True)


class TurbovecBackend:
    """Local TurboQuant vector backend with a JSON metadata sidecar.

    Vectors are normalized before indexing and searching, so inner-product scores
    have cosine semantics. Snapshots store the compressed index and its metadata
    sidecar in the same directory.
    """

    def __init__(
        self,
        snapshot_path: str | Path | None = None,
        *,
        metric: DistanceMetric = DistanceMetric.COSINE,
        bit_width: int = 4,
    ) -> None:
        """Create a local Turbovec backend.

        Args:
            snapshot_path: Optional manifest path for a persistent snapshot.
                Its referenced index and payload files must stay beside it.
            metric: Similarity metric. Only cosine is supported.
            bit_width: TurboQuant compression width. Must be 2, 3, or 4.
        """
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
        self._dirty = False
        if self._snapshot_path is not None and self._snapshot_path.exists():
            self._load_snapshot(self._snapshot_path)

    def _load_snapshot(self, snapshot_path: Path) -> None:
        while True:
            manifest = self._read_manifest(snapshot_path)
            try:
                index, payloads, id_to_uint, uint_to_id = (
                    self._load_snapshot_generation(snapshot_path, manifest)
                )
            except FileNotFoundError as exc:
                if self._read_manifest(snapshot_path) != manifest:
                    continue
                raise ValueError("Turbovec snapshot references missing files") from exc
            if self._read_manifest(snapshot_path) != manifest:
                continue
            self._index = index
            self._payloads = payloads
            self._id_to_uint = id_to_uint
            self._uint_to_id = uint_to_id
            self._bit_width = index.bit_width
            return

    def _read_manifest(self, snapshot_path: Path) -> dict[str, Any]:
        try:
            manifest = json.loads(snapshot_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("invalid Turbovec snapshot manifest") from exc
        if (
            not isinstance(manifest, dict)
            or not {"index", "payloads"} <= manifest.keys()
        ):
            raise ValueError("invalid Turbovec snapshot manifest")
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
        return manifest

    def _load_snapshot_generation(
        self, snapshot_path: Path, manifest: dict[str, Any]
    ) -> tuple[Any, dict[str, dict[str, Any]], dict[str, int], dict[int, str]]:
        index_name, payload_name = manifest["index"], manifest["payloads"]
        try:
            data = json.loads(
                (snapshot_path.parent / payload_name).read_text(encoding="utf-8")
            )
        except json.JSONDecodeError as exc:
            raise ValueError("invalid Turbovec snapshot payloads") from exc
        if (
            not isinstance(data, dict)
            or not {"ids", "payloads"} <= data.keys()
            or not isinstance(data["ids"], dict)
            or not isinstance(data["payloads"], dict)
        ):
            raise ValueError("invalid Turbovec snapshot payloads")
        ids = data["ids"]
        payloads = data["payloads"]
        if (
            any(not isinstance(key, str) for key in ids)
            or any(type(value) is not int for value in ids.values())
            or any(
                not isinstance(key, str) or not isinstance(value, dict)
                for key, value in payloads.items()
            )
        ):
            raise ValueError("invalid Turbovec snapshot payloads")
        id_to_uint = dict(ids)
        uint_to_id = {value: key for key, value in id_to_uint.items()}
        if (
            set(id_to_uint) != set(payloads)
            or len(uint_to_id) != len(id_to_uint)
            or any(value < 0 or value >= 1 << 64 for value in id_to_uint.values())
        ):
            raise ValueError("inconsistent Turbovec snapshot index and payloads")

        index = _import_id_map_index().load(str(snapshot_path.parent / index_name))
        if len(payloads) != len(index) or any(
            uid not in index for uid in id_to_uint.values()
        ):
            raise ValueError("inconsistent Turbovec snapshot index and payloads")
        return index, payloads, id_to_uint, uint_to_id

    def _candidate_id(self, id_: str) -> int:
        current = self._id_to_uint.get(id_)
        if current is not None:
            return current
        candidate = int.from_bytes(
            hashlib.blake2b(id_.encode(), digest_size=8).digest(), "big"
        )
        while candidate in self._uint_to_id and self._uint_to_id[candidate] != id_:
            candidate = (candidate + 1) & ((1 << 64) - 1)
        return candidate

    async def _await_thread(self, operation: Callable[[], _T]) -> tuple[_T, bool]:
        task = asyncio.create_task(asyncio.to_thread(operation))
        cancelled = False
        while True:
            try:
                return await asyncio.shield(task), cancelled
            except asyncio.CancelledError:
                if task.cancelled():
                    raise
                cancelled = True

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
        id_map_index = _import_id_map_index()
        self._index = await asyncio.to_thread(
            id_map_index, dim=dim, bit_width=self._bit_width
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
            existed = id in self._payloads
            uid = self._candidate_id(id)

            def update_index() -> None:
                if existed:
                    index.remove(uid)
                index.add_with_ids(
                    normalized.reshape(1, -1),
                    np.asarray([uid], dtype=np.uint64),
                )

            try:
                _, cancelled = await self._await_thread(update_index)
            except BaseException:
                if existed and uid not in index:
                    self._drop_ids([id])
                    self._mark_dirty()
                    await self._flush()
                elif not existed and uid in index:
                    self._id_to_uint[id] = uid
                    self._uint_to_id[uid] = id
                    self._payloads[id] = value
                    self._mark_dirty()
                    await self._flush()
                raise
            self._id_to_uint[id] = uid
            self._uint_to_id[uid] = id
            self._payloads[id] = value
            self._mark_dirty()
            await self._flush()
            if cancelled:
                raise asyncio.CancelledError

    async def search(
        self, vector: list[float], top_k: int, filters: dict
    ) -> list[tuple[str, float, dict]]:
        if top_k <= 0:
            return []
        normalized = _unit(vector)
        async with self._lock:
            if self._index is None or len(self._index) == 0:
                return []
            if self._index.dim is not None and self._index.dim != normalized.size:
                raise ValueError(
                    f"vector dimension changed from {self._index.dim} to {normalized.size}"
                )
            allowed = None
            if filters:
                allowed_ids = [
                    self._id_to_uint[key]
                    for key, payload in self._payloads.items()
                    if _matches(payload, filters)
                ]
                if not allowed_ids:
                    return []
                allowed = np.asarray(allowed_ids, dtype=np.uint64)
                result_count = min(top_k, len(allowed_ids))
            else:
                result_count = min(top_k, len(self._index))

            def search_index():
                return self._index.search(
                    normalized.reshape(1, -1),
                    result_count,
                    allowlist=allowed,
                )

            (scores, ids), cancelled = await self._await_thread(search_index)
            results = [
                (
                    self._uint_to_id[int(uid)],
                    float(score),
                    dict(self._payloads[self._uint_to_id[int(uid)]]),
                )
                for score, uid in zip(scores[0], ids[0])
                if int(uid) in self._uint_to_id
                and self._uint_to_id[int(uid)] in self._payloads
            ]
            if cancelled:
                raise asyncio.CancelledError
            return results

    async def delete(self, id: str) -> None:
        async with self._lock:
            uid = self._id_to_uint.get(id)
            if id not in self._payloads or uid is None:
                await self._flush()
                return
            index = self._index
            if index is not None:
                try:
                    _, cancelled = await self._await_thread(lambda: index.remove(uid))
                except BaseException:
                    if uid not in index:
                        self._drop_ids([id])
                        self._mark_dirty()
                        await self._flush()
                    raise
            else:
                cancelled = False
            self._drop_ids([id])
            self._mark_dirty()
            await self._flush()
            if cancelled:
                raise asyncio.CancelledError

    async def delete_where(self, filters: dict) -> None:
        async with self._lock:
            if not filters:
                await self._flush()
                return
            removals = [
                key
                for key, payload in self._payloads.items()
                if _matches(payload, filters)
            ]
            if not removals:
                await self._flush()
                return
            index = self._index
            if index is not None:
                removed: list[str] = []

                def remove_index_entries() -> None:
                    for key in removals:
                        index.remove(self._id_to_uint[key])
                        removed.append(key)

                try:
                    _, cancelled = await self._await_thread(remove_index_entries)
                except BaseException:
                    self._drop_ids(removed)
                    if removed:
                        self._mark_dirty()
                    await self._flush()
                    raise
            else:
                cancelled = False
            self._drop_ids(removals)
            self._mark_dirty()
            await self._flush()
            if cancelled:
                raise asyncio.CancelledError

    async def list_where(self, filters: dict, limit: int) -> list[tuple[str, dict]]:
        if limit <= 0:
            return []
        async with self._lock:
            matches: list[tuple[str, dict[str, Any]]] = []
            for key, value in self._payloads.items():
                if _matches(value, filters):
                    matches.append((key, dict(value)))
                    if len(matches) >= limit:
                        break
            return matches

    async def count(self, filters: dict) -> int:
        async with self._lock:
            if not filters:
                return len(self._payloads)
            return sum(
                _matches(payload, filters) for payload in self._payloads.values()
            )

    def _drop_ids(self, ids: list[str]) -> None:
        for id_ in ids:
            self._payloads.pop(id_, None)
            uid = self._id_to_uint.pop(id_, None)
            if uid is not None:
                self._uint_to_id.pop(uid, None)

    def _mark_dirty(self) -> None:
        if self._snapshot_path is not None:
            self._dirty = True

    async def _flush(self) -> None:
        if self._snapshot_path is None or self._index is None or not self._dirty:
            return
        content = json.dumps(
            {"ids": self._id_to_uint, "payloads": self._payloads},
            ensure_ascii=False,
            allow_nan=False,
        )
        _, cancelled = await self._await_thread(lambda: self._write_snapshot(content))
        self._dirty = False
        if cancelled:
            raise asyncio.CancelledError

    def _write_snapshot(self, content: str) -> None:
        snapshot_path = self._snapshot_path
        index = self._index
        if snapshot_path is None or index is None:
            return
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        previous = _read_snapshot_manifest(snapshot_path)
        generation = secrets.token_hex(16)
        index_name = f"{snapshot_path.name}.{generation}.tvim"
        payload_name = f"{snapshot_path.name}.{generation}.payloads.json"
        index_path = snapshot_path.parent / index_name
        payload_path = snapshot_path.parent / payload_name
        committed = False
        try:
            index.write(str(index_path), durable=True)
            _write_fsynced_file(payload_path, content, f".{payload_name}.")
            manifest = json.dumps({"index": index_name, "payloads": payload_name})
            _write_fsynced_file(snapshot_path, manifest, f".{snapshot_path.name}.")
            committed = True
            _fsync_directory(snapshot_path.parent)
            _remove_previous_snapshot_files(
                snapshot_path, previous, (index_path, payload_path)
            )
        finally:
            if not committed:
                for orphan in (index_path, payload_path):
                    with suppress(OSError):
                        orphan.unlink(missing_ok=True)
