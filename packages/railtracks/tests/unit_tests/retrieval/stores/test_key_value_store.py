"""Tests for retrieval/stores/key_value — KeyValueStore + InMemoryKeyValueStore."""

from __future__ import annotations

import asyncio

from railtracks.retrieval.stores.key_value import (
    InMemoryKeyValueStore,
    KeyValueStore,
)

# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class _IncompleteStore:
    async def set(self, key: str, value: str) -> None:
        pass

    async def get(self, key: str) -> str | None:
        return None

    # missing delete, keys, items, clear


def test_in_memory_store_satisfies_protocol():
    assert isinstance(InMemoryKeyValueStore(), KeyValueStore)


def test_incomplete_implementation_fails_protocol():
    assert not isinstance(_IncompleteStore(), KeyValueStore)


# ---------------------------------------------------------------------------
# Core read/write behaviour
# ---------------------------------------------------------------------------


async def test_set_get_roundtrip():
    store = InMemoryKeyValueStore()
    await store.set("salary", "80k/year")
    assert await store.get("salary") == "80k/year"


async def test_get_missing_returns_none():
    store = InMemoryKeyValueStore()
    assert await store.get("nope") is None


async def test_set_overwrites():
    store = InMemoryKeyValueStore()
    await store.set("goal", "buy a house")
    await store.set("goal", "buy a boat")
    assert await store.get("goal") == "buy a boat"


async def test_delete_removes_key():
    store = InMemoryKeyValueStore()
    await store.set("debt", "10k")
    await store.delete("debt")
    assert await store.get("debt") is None


async def test_delete_missing_is_noop():
    store = InMemoryKeyValueStore()
    # Should not raise.
    await store.delete("never-set")


async def test_keys_and_items():
    store = InMemoryKeyValueStore()
    await store.set("a", "1")
    await store.set("b", "2")
    assert sorted(await store.keys()) == ["a", "b"]
    assert await store.items() == {"a": "1", "b": "2"}


async def test_items_returns_copy():
    store = InMemoryKeyValueStore()
    await store.set("a", "1")
    snapshot = await store.items()
    snapshot["a"] = "mutated"
    snapshot["b"] = "injected"
    assert await store.items() == {"a": "1"}


async def test_clear():
    store = InMemoryKeyValueStore()
    await store.set("a", "1")
    await store.set("b", "2")
    await store.clear()
    assert await store.keys() == []
    assert await store.items() == {}


# ---------------------------------------------------------------------------
# Persistence via snapshot_path
# ---------------------------------------------------------------------------


async def test_snapshot_persists_across_instances(tmp_path):
    path = tmp_path / "memory.json"

    store = InMemoryKeyValueStore(snapshot_path=path)
    await store.set("salary", "80k/year")
    await store.set("goal", "buy a house")

    reloaded = InMemoryKeyValueStore(snapshot_path=path)
    assert await reloaded.get("salary") == "80k/year"
    assert await reloaded.items() == {"salary": "80k/year", "goal": "buy a house"}


async def test_snapshot_reflects_delete_and_clear(tmp_path):
    path = tmp_path / "memory.json"

    store = InMemoryKeyValueStore(snapshot_path=path)
    await store.set("a", "1")
    await store.set("b", "2")
    await store.delete("a")
    assert await InMemoryKeyValueStore(snapshot_path=path).items() == {"b": "2"}

    await store.clear()
    assert await InMemoryKeyValueStore(snapshot_path=path).items() == {}


async def test_no_snapshot_means_ephemeral():
    store = InMemoryKeyValueStore()
    await store.set("a", "1")
    # A fresh instance shares nothing.
    assert await InMemoryKeyValueStore().items() == {}


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------


async def test_concurrent_sets_all_land():
    store = InMemoryKeyValueStore()
    await asyncio.gather(*(store.set(f"k{i}", str(i)) for i in range(50)))
    items = await store.items()
    assert len(items) == 50
    assert items["k7"] == "7"
