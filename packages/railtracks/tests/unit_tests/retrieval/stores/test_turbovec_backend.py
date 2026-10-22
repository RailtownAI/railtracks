from __future__ import annotations

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


async def test_protocol_filter_normalization_and_stable_ids(tmp_path) -> None:
    backend = TurbovecBackend()
    await backend.upsert(
        "one", [10.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], {"tenant": "a"}
    )
    await backend.upsert(
        "two", [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], {"tenant": "b"}
    )
    assert await backend.count({}) == 2
    assert await backend.count({"tenant": "a"}) == 1
    assert await backend.list_where({"tenant": "b"}, 2) == [("two", {"tenant": "b"})]
    assert (
        await backend.search(
            [7.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], 5, {"tenant": "a"}
        )
    )[0][0] == "one"
    stable_id = backend._id_to_uint["one"]
    await backend.delete("one")
    await backend.upsert(
        "one", [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0], {"tenant": "a"}
    )
    assert backend._id_to_uint["one"] == stable_id
    await backend.delete_where({"tenant": "b"})
    assert await backend.count({}) == 1


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


async def test_empty_allowlist_and_bad_dimension_are_safe() -> None:
    backend = TurbovecBackend()
    assert await backend.search([1.0] * 8, 3, {}) == []
    await backend.upsert("seed", [1.0] * 8, {})
    with pytest.raises(ValueError, match="dimension"):
        await backend.upsert("id", [1.0] * 16, {})
    with pytest.raises(ValueError, match="finite"):
        await backend.upsert("bad", [float("inf")] * 8, {})
