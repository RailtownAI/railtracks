from unittest.mock import MagicMock

import pytest
from railtracks.prebuilt.tools.memory import KeyValueMemoryToolSet
from railtracks.retrieval.stores.key_value import InMemoryKeyValueStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ts():
    return KeyValueMemoryToolSet()


# ---------------------------------------------------------------------------
# remember / recall
# ---------------------------------------------------------------------------


async def test_remember_then_recall(ts):
    await ts.remember("user_timezone", "PST")
    assert await ts.recall("user_timezone") == "PST"


async def test_recall_missing_key(ts):
    out = await ts.recall("nope")
    assert "No memory found" in out
    assert "nope" in out


async def test_remember_overwrites(ts):
    await ts.remember("goal", "buy a house")
    await ts.remember("goal", "buy a boat")
    assert await ts.recall("goal") == "buy a boat"


async def test_remember_returns_confirmation(ts):
    out = await ts.remember("k", "v")
    assert "k" in out and "v" in out


# ---------------------------------------------------------------------------
# forget
# ---------------------------------------------------------------------------


async def test_forget_existing_key(ts):
    await ts.remember("debt", "10k")
    out = await ts.forget("debt")
    assert "Forgot" in out
    assert await ts.recall("debt") == "No memory found under key 'debt'."


async def test_forget_missing_key_is_noop(ts):
    out = await ts.forget("never-set")
    assert "Nothing was stored" in out


# ---------------------------------------------------------------------------
# list_memories / search_memories
# ---------------------------------------------------------------------------


async def test_list_memories_empty(ts):
    assert await ts.list_memories() == "No memories stored."


async def test_list_memories_populated(ts):
    await ts.remember("a", "1")
    await ts.remember("b", "2")
    out = await ts.list_memories()
    assert "a: 1" in out
    assert "b: 2" in out


async def test_list_keys_empty(ts):
    assert await ts.list_keys() == "No memories stored."


async def test_list_keys_populated(ts):
    await ts.remember("a", "1")
    await ts.remember("b", "2")
    out = await ts.list_keys()
    assert "- a" in out
    assert "- b" in out
    # values must not leak into a keys-only listing
    assert "1" not in out
    assert "2" not in out


async def test_search_matches_key_and_value_case_insensitive(ts):
    await ts.remember("favorite_color", "blue")
    await ts.remember("pet", "a Blue parrot")
    out = await ts.search_memories("BLUE")
    assert "favorite_color: blue" in out
    assert "pet: a Blue parrot" in out


async def test_search_no_match(ts):
    await ts.remember("a", "1")
    out = await ts.search_memories("zzz")
    assert "No memories matched" in out


# ---------------------------------------------------------------------------
# Store injection / persistence / isolation
# ---------------------------------------------------------------------------


async def test_defaults_to_in_memory_store(ts):
    assert isinstance(ts.store, InMemoryKeyValueStore)


async def test_injected_store_is_used():
    store = InMemoryKeyValueStore()
    ts = KeyValueMemoryToolSet(store=store)
    await ts.remember("k", "v")
    assert await store.get("k") == "v"


async def test_persistence_via_snapshot_path(tmp_path):
    path = tmp_path / "memory.json"
    ts1 = KeyValueMemoryToolSet(store=InMemoryKeyValueStore(snapshot_path=path))
    await ts1.remember("salary", "80k")

    ts2 = KeyValueMemoryToolSet(store=InMemoryKeyValueStore(snapshot_path=path))
    assert await ts2.recall("salary") == "80k"


async def test_instances_are_isolated():
    t1 = KeyValueMemoryToolSet()
    t2 = KeyValueMemoryToolSet()
    await t1.remember("k", "v")
    assert await t2.list_memories() == "No memories stored."


# ---------------------------------------------------------------------------
# on_change callback
# ---------------------------------------------------------------------------


async def test_on_change_fires_on_remember_and_forget():
    cb = MagicMock()
    ts = KeyValueMemoryToolSet(on_change=cb)
    await ts.remember("k", "v")
    cb.assert_called_with("k", "v")
    await ts.forget("k")
    cb.assert_called_with("k", None)


async def test_on_change_exception_is_swallowed():
    cb = MagicMock(side_effect=RuntimeError("boom"))
    ts = KeyValueMemoryToolSet(on_change=cb)
    # Should not raise despite the callback blowing up.
    out = await ts.remember("k", "v")
    assert "k" in out
    assert await ts.recall("k") == "v"


# ---------------------------------------------------------------------------
# tool_set() / prompt()
# ---------------------------------------------------------------------------


def test_tool_set_returns_rt_functions(ts):
    tools = ts.tool_set()
    assert len(tools) == 6
    assert all(hasattr(t, "node_type") for t in tools)


async def test_tool_set_bound_to_instance():
    t1 = KeyValueMemoryToolSet()
    remember_tool = t1.tool_set()[0]
    await remember_tool("k", "v")
    assert await t1.recall("k") == "v"


def test_prompt_is_non_empty_string():
    result = KeyValueMemoryToolSet.prompt()
    assert isinstance(result, str)
    assert len(result) > 0
