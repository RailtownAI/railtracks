from __future__ import annotations

import asyncio
import builtins
import json
import threading
from pathlib import Path
from uuid import uuid4

import numpy as np
import pytest
from railtracks.retrieval.stores import (
    DistanceMetric,
    StoreEntry,
    StoreQuery,
    StoreScope,
    TurbovecBackend,
    VectorStore,
)
from railtracks.retrieval.stores.vector.backends import turbovec as turbovec_module
from railtracks.retrieval.stores.vector.backends.turbovec import _unit


@pytest.fixture
def require_turbovec() -> None:
    pytest.importorskip("turbovec")


def test_unit_rejects_non_finite_and_normalizes_in_float64() -> None:
    np.testing.assert_allclose(_unit([3.0, 4.0]), [0.6, 0.8])
    assert _unit([0.0, 0.0]).dtype == np.float32
    np.testing.assert_array_equal(_unit([0.0, 0.0]), [0.0, 0.0])
    np.testing.assert_allclose(_unit([1e20, 0.0]), [1.0, 0.0])
    np.testing.assert_allclose(_unit([1e-25, 0.0]), [1.0, 0.0])
    np.testing.assert_allclose(_unit([1e200, 0.0]), [1.0, 0.0])
    np.testing.assert_allclose(_unit([1e-200, 0.0]), [1.0, 0.0])
    with pytest.raises(ValueError, match="finite"):
        _unit([float("nan")])
    with pytest.raises(ValueError, match="finite"):
        _unit([float("inf")])
    with pytest.raises(ValueError, match="non-empty"):
        _unit([])
    with pytest.raises(ValueError, match="one-dimensional"):
        _unit([[1.0, 0.0]])


def test_constructor_validates_configuration_without_optional_dependency() -> None:
    with pytest.raises(ValueError, match="cosine"):
        TurbovecBackend(metric=DistanceMetric.L2)
    with pytest.raises(ValueError, match="2, 3, or 4"):
        TurbovecBackend(bit_width=8)


def test_backend_is_reexported_from_stores_package() -> None:
    from railtracks.retrieval.stores import TurbovecBackend as ExportedBackend

    assert ExportedBackend is TurbovecBackend


async def test_import_error_is_clear_for_ready_and_snapshot_load(
    tmp_path, monkeypatch
) -> None:
    original_import = builtins.__import__

    def without_turbovec(name, *args, **kwargs):
        if name == "turbovec":
            raise ImportError("not installed")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_turbovec)
    with pytest.raises(ImportError, match="stores-turbovec"):
        await TurbovecBackend()._ready(8)

    snapshot = tmp_path / "vectors.json"
    snapshot.write_text(
        json.dumps({"index": "vectors.tvim", "payloads": "vectors.payloads.json"}),
        encoding="utf-8",
    )
    (tmp_path / "vectors.payloads.json").write_text(
        json.dumps({"ids": {}, "payloads": {}}), encoding="utf-8"
    )
    with pytest.raises(ImportError, match="stores-turbovec"):
        TurbovecBackend(snapshot)


@pytest.mark.parametrize(
    "manifest",
    [
        [],
        {"index": "vectors.tvim"},
        {"index": "../vectors.tvim", "payloads": "vectors.payloads.json"},
        {"index": 4, "payloads": "vectors.payloads.json"},
    ],
)
def test_corrupt_snapshot_manifest_is_rejected_without_optional_dependency(
    tmp_path, manifest
) -> None:
    snapshot = tmp_path / "vectors.json"
    snapshot.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="manifest"):
        TurbovecBackend(snapshot)


@pytest.mark.parametrize(
    "data",
    [
        None,
        {"ids": {"record": True}, "payloads": {"record": {}}},
        {"ids": {"record": 1}, "payloads": {}},
    ],
)
def test_corrupt_snapshot_payloads_are_rejected_without_optional_dependency(
    tmp_path, data
) -> None:
    snapshot = tmp_path / "vectors.json"
    snapshot.write_text(
        json.dumps({"index": "vectors.tvim", "payloads": "vectors.payloads.json"}),
        encoding="utf-8",
    )
    (tmp_path / "vectors.payloads.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="payloads|inconsistent"):
        TurbovecBackend(snapshot)


async def test_protocol_filter_normalization_and_stable_ids(require_turbovec) -> None:
    backend = TurbovecBackend()
    await backend.upsert(
        "one", [10.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], {"tenant": "a"}
    )
    await backend.upsert(
        "two", [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], {"tenant": "b"}
    )
    await backend.upsert(
        "three", [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0], {"tenant": "a"}
    )
    assert await backend.count({}) == 3
    assert await backend.count({"tenant": "a"}) == 2
    assert await backend.list_where({"tenant": "b"}, 2) == [("two", {"tenant": "b"})]
    filtered = await backend.search([1.0] + [0.0] * 7, 2, {"tenant": "a"})
    assert {record[0] for record in filtered} == {"one", "three"}
    assert len(filtered) == 2
    assert filtered[0][0] == "one"
    assert filtered[0][1] > 0.9

    stable_id = backend._id_to_uint["one"]
    await backend.upsert("one", [0.0, 0.0, 0.0, 1.0] + [0.0] * 4, {"tenant": "b"})
    assert await backend.count({}) == 3
    assert await backend.count({"tenant": "a"}) == 1
    assert backend._id_to_uint["one"] == stable_id
    assert (await backend.search([0.0, 0.0, 0.0, 1.0] + [0.0] * 4, 1, {}))[0][
        0
    ] == "one"

    await backend.delete("one")
    assert "one" not in backend._id_to_uint
    assert stable_id not in backend._uint_to_id
    await backend.upsert(
        "one", [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0], {"tenant": "a"}
    )
    assert backend._id_to_uint["one"] == stable_id
    await backend.delete_where({"tenant": "b"})
    assert "two" not in backend._id_to_uint
    assert await backend.count({}) == 2


async def test_snapshot_round_trip_uses_atomic_manifest(
    require_turbovec, tmp_path
) -> None:
    snapshot = tmp_path / "vectors.json"
    backend = TurbovecBackend(snapshot)
    await backend.upsert("record", [1.0] + [0.0] * 7, {"scope_user_id": "alice"})
    manifest = json.loads(snapshot.read_text())
    assert (tmp_path / manifest["index"]).is_file()
    assert (tmp_path / manifest["payloads"]).is_file()
    restored = TurbovecBackend(snapshot)
    assert await restored.count({"scope_user_id": "alice"}) == 1
    assert (await restored.search([1.0] + [0.0] * 7, 1, {}))[0][0] == "record"
    stable_id = restored._id_to_uint["record"]
    await restored.upsert("record", [0.0, 1.0] + [0.0] * 6, {"scope_user_id": "bob"})
    reopened = TurbovecBackend(snapshot)
    assert reopened._id_to_uint["record"] == stable_id
    assert await reopened.count({"scope_user_id": "bob"}) == 1
    assert await reopened.count({"scope_user_id": "alice"}) == 0
    await reopened.delete("record")
    assert await TurbovecBackend(snapshot).count({}) == 0


async def test_snapshot_no_op_deletes_do_not_rewrite_manifest(
    require_turbovec, tmp_path
) -> None:
    snapshot = tmp_path / "vectors.json"
    backend = TurbovecBackend(snapshot)
    await backend.upsert("record", [1.0] + [0.0] * 7, {"tenant": "a"})
    original_manifest = snapshot.read_text(encoding="utf-8")
    await backend.delete("missing")
    await backend.delete_where({"tenant": "missing"})
    await backend.delete_where({})
    assert snapshot.read_text(encoding="utf-8") == original_manifest


@pytest.mark.parametrize("delete_method", ["delete", "delete_where"])
async def test_delete_retry_flushes_a_pending_snapshot(
    require_turbovec, tmp_path, delete_method
) -> None:
    snapshot = tmp_path / "vectors.json"
    backend = TurbovecBackend(snapshot)
    await backend.upsert("record", [1.0] + [0.0] * 7, {"tenant": "a"})
    original_manifest = snapshot.read_text(encoding="utf-8")
    write_snapshot = backend._write_snapshot

    def fail_write(content: str) -> None:
        raise OSError("simulated snapshot write failure")

    backend._write_snapshot = fail_write
    with pytest.raises(OSError, match="simulated snapshot write failure"):
        if delete_method == "delete":
            await backend.delete("record")
        else:
            await backend.delete_where({"tenant": "a"})
    assert await backend.count({}) == 0
    assert backend._dirty

    backend._write_snapshot = write_snapshot
    if delete_method == "delete":
        await backend.delete("record")
    else:
        await backend.delete_where({"tenant": "a"})
    assert not backend._dirty
    assert snapshot.read_text(encoding="utf-8") != original_manifest
    assert await TurbovecBackend(snapshot).count({}) == 0


async def test_snapshot_reader_retries_after_generation_is_replaced(
    require_turbovec, tmp_path, monkeypatch
) -> None:
    snapshot = tmp_path / "vectors.json"
    backend = TurbovecBackend(snapshot)
    await backend.upsert("first", [1.0] + [0.0] * 7, {})
    original_read_text = Path.read_text
    manifest_captured = threading.Event()
    resume_reader = threading.Event()

    def pause_reader_after_manifest(path, *args, **kwargs):
        content = original_read_text(path, *args, **kwargs)
        if path == snapshot and not manifest_captured.is_set():
            manifest_captured.set()
            if not resume_reader.wait(timeout=5):
                raise TimeoutError("timed out waiting to resume snapshot reader")
        return content

    monkeypatch.setattr(Path, "read_text", pause_reader_after_manifest)
    reader = asyncio.create_task(asyncio.to_thread(TurbovecBackend, snapshot))
    assert await asyncio.to_thread(manifest_captured.wait, 5)
    try:
        await backend.upsert("second", [0.0, 1.0] + [0.0] * 6, {})
    finally:
        resume_reader.set()

    restored = await reader
    assert await restored.count({}) == 2


async def test_snapshot_cleanup_tolerates_open_old_sidecar(
    require_turbovec, tmp_path, monkeypatch
) -> None:
    snapshot = tmp_path / "vectors.json"
    backend = TurbovecBackend(snapshot)
    await backend.upsert("first", [1.0] + [0.0] * 7, {})
    manifest = json.loads(snapshot.read_text(encoding="utf-8"))
    old_payload = tmp_path / manifest["payloads"]
    original_unlink = Path.unlink

    def block_old_payload(path, *args, **kwargs):
        if path == old_payload:
            raise PermissionError("simulated open sidecar")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", block_old_payload)
    await backend.upsert("second", [0.0, 1.0] + [0.0] * 6, {})

    assert old_payload.is_file()
    assert await TurbovecBackend(snapshot).count({}) == 2


async def test_snapshot_cleanup_preserves_files_owned_by_another_manifest(
    require_turbovec, tmp_path
) -> None:
    original_snapshot = tmp_path / "original.json"
    original = TurbovecBackend(original_snapshot)
    await original.upsert("first", [1.0] + [0.0] * 7, {})
    original_manifest = json.loads(original_snapshot.read_text(encoding="utf-8"))
    original_files = [
        tmp_path / original_manifest["index"],
        tmp_path / original_manifest["payloads"],
    ]

    copied_snapshot = tmp_path / "branch.json"
    copied_snapshot.write_text(
        original_snapshot.read_text(encoding="utf-8"), encoding="utf-8"
    )
    copied = TurbovecBackend(copied_snapshot)
    await copied.upsert("second", [0.0, 1.0] + [0.0] * 6, {})

    assert all(path.is_file() for path in original_files)
    assert await TurbovecBackend(original_snapshot).count({}) == 1
    assert await TurbovecBackend(copied_snapshot).count({}) == 2


async def test_snapshot_manifest_replace_retries_permission_error(
    require_turbovec, tmp_path, monkeypatch
) -> None:
    snapshot = tmp_path / "vectors.json"
    backend = TurbovecBackend(snapshot)
    await backend.upsert("first", [1.0] + [0.0] * 7, {})
    original_replace = turbovec_module.os.replace
    failures_remaining = 1

    def fail_manifest_once(source, destination):
        nonlocal failures_remaining
        if destination == snapshot and failures_remaining:
            failures_remaining -= 1
            raise PermissionError("simulated manifest sharing violation")
        return original_replace(source, destination)

    monkeypatch.setattr(turbovec_module.os, "replace", fail_manifest_once)
    await backend.upsert("second", [0.0, 1.0] + [0.0] * 6, {})

    assert failures_remaining == 0
    assert await TurbovecBackend(snapshot).count({}) == 2


async def test_concurrent_upserts_and_searches_are_serialized(require_turbovec) -> None:
    backend = TurbovecBackend()
    vectors = [[float(i == dimension) for dimension in range(8)] for i in range(8)]
    await asyncio.gather(
        *(
            backend.upsert(f"id-{index}", vector, {"group": index % 2})
            for index, vector in enumerate(vectors)
        )
    )
    found = await asyncio.gather(
        *(
            backend.search(vector, 2, {"group": index % 2})
            for index, vector in enumerate(vectors)
        )
    )
    assert await backend.count({}) == 8
    assert all(
        any(item[0] == f"id-{i}" for item in results) for i, results in enumerate(found)
    )


async def test_cancelled_upsert_finishes_index_and_metadata_together(
    require_turbovec,
) -> None:
    backend = TurbovecBackend()
    await backend._ready(8)
    index = backend._index
    entered = threading.Event()
    release = threading.Event()

    class DelayedIndex:
        def __getattr__(self, name):
            return getattr(index, name)

        def __len__(self):
            return len(index)

        def __contains__(self, uid):
            return uid in index

        def add_with_ids(self, *args, **kwargs):
            entered.set()
            if not release.wait(timeout=5):
                raise TimeoutError("timed out waiting to release test index")
            return index.add_with_ids(*args, **kwargs)

    backend._index = DelayedIndex()
    pending = asyncio.create_task(
        backend.upsert("cancelled", [1.0] + [0.0] * 7, {"group": "a"})
    )
    assert await asyncio.to_thread(entered.wait, 5)
    pending.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await pending
    assert await backend.count({}) == 1
    assert backend._id_to_uint["cancelled"] in backend._index


async def test_failed_replacement_does_not_leave_a_payload_without_an_index(
    require_turbovec,
) -> None:
    backend = TurbovecBackend()
    await backend.upsert("record", [1.0] + [0.0] * 7, {"group": "a"})
    index = backend._index

    class FailingIndex:
        def __getattr__(self, name):
            return getattr(index, name)

        def __len__(self):
            return len(index)

        def __contains__(self, uid):
            return uid in index

        def add_with_ids(self, *args, **kwargs):
            raise RuntimeError("simulated index insertion failure")

    backend._index = FailingIndex()
    with pytest.raises(RuntimeError, match="simulated index insertion failure"):
        await backend.upsert("record", [0.0, 1.0] + [0.0] * 6, {"group": "b"})

    assert await backend.count({}) == 0
    assert backend._id_to_uint == {}
    assert backend._uint_to_id == {}
    assert len(backend._index) == 0


async def test_search_and_listing_edge_cases(require_turbovec) -> None:
    backend = TurbovecBackend()
    assert await backend.search([1.0] * 8, 3, {}) == []
    await backend.upsert("seed", [1.0] + [0.0] * 7, {"tenant": "a"})
    await backend.upsert("other", [0.0, 1.0] + [0.0] * 6, {"tenant": "a"})

    assert await backend.search([1.0] * 8, 0, {}) == []
    assert await backend.search([1.0] * 8, -1, {}) == []
    assert await backend.search([1.0] * 8, 3, {"tenant": "missing"}) == []
    with pytest.raises(ValueError, match="dimension"):
        await backend.search([1.0] * 16, 1, {})
    assert await backend.list_where({}, 0) == []
    assert len(await backend.list_where({}, 1)) == 1
    assert len(await backend.list_where({}, 10)) == 2
    assert await backend.delete_where({}) is None


async def test_vector_store_round_trip(require_turbovec) -> None:
    vector = [1.0] + [0.0] * 7
    scope = StoreScope(labels={"user_id": "alice"})
    entry = StoreEntry(
        id=uuid4(),
        content="hello turbovec",
        vector=vector,
        embedding_model="test-model",
        chunk_id=uuid4(),
        document_id=uuid4(),
        scope=scope,
        chunk_metadata={"category": "guide"},
    )
    store = VectorStore(TurbovecBackend())

    await store.write(entry)
    results = await store.read(
        StoreQuery(
            text="hello",
            scope=scope,
            embedding=vector,
            top_k=3,
            metadata_filters={"category": "guide"},
        )
    )
    assert [result.entry.id for result in results] == [entry.id]
    assert [item.id for item in await store.find({"category": "guide"})] == [entry.id]
    assert await store.count({"category": "guide"}) == 1
    nearest = await store.nearest_neighbors(vector, 1, scope=scope)
    assert [result.entry.id for result in nearest] == [entry.id]

    await store.delete(entry.id)
    assert await store.count() == 0
    await store.write(entry)
    await store.clear(scope)
    assert await store.count() == 0
