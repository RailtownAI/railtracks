from __future__ import annotations

import asyncio
import json

import numpy as np
import pytest

pytest.importorskip("turbovec")

from railtracks.retrieval.stores.vector.backends.turbovec import TurbovecBackend, _unit


def test_unit_rejects_non_finite_and_normalizes() -> None:
    np.testing.assert_allclose(_unit([3.0, 4.0]), [0.6, 0.8])
    np.testing.assert_array_equal(_unit([0.0, 0.0]), [0.0, 0.0])
    with pytest.raises(ValueError, match="finite"):
        _unit([float("nan")])
    with pytest.raises(ValueError, match="finite"):
        _unit([float("inf")])
    with pytest.raises(ValueError, match="non-empty"):
        _unit([])
    with pytest.raises(ValueError, match="one-dimensional"):
        _unit([[1.0, 0.0]])


async def test_protocol_filter_normalization_and_stable_ids() -> None:
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
    await backend.upsert(
        "one", [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0], {"tenant": "a"}
    )
    assert backend._id_to_uint["one"] == stable_id
    await backend.delete_where({"tenant": "b"})
    assert await backend.count({}) == 2


async def test_snapshot_round_trip_uses_atomic_manifest(tmp_path) -> None:
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


async def test_concurrent_upserts_and_searches_are_serialized() -> None:
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


async def test_empty_allowlist_and_bad_dimension_are_safe() -> None:
    backend = TurbovecBackend()
    assert await backend.search([1.0] * 8, 3, {}) == []
    await backend.upsert("seed", [1.0] * 8, {})
    with pytest.raises(ValueError, match="dimension"):
        await backend.upsert("id", [1.0] * 16, {})
    with pytest.raises(ValueError, match="finite"):
        await backend.upsert("bad", [float("inf")] * 8, {})
    with pytest.raises(ValueError, match="multiple of 8"):
        await TurbovecBackend().upsert("bad-dimension", [1.0] * 7, {})
