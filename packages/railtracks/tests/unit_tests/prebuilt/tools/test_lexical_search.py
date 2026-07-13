"""Tests for prebuilt/tools/memory/search — LexicalSearch + LexicalSearchConfig."""

from __future__ import annotations

from railtracks.prebuilt.tools.memory.search import (
    LexicalSearch,
    LexicalSearchConfig,
    SearchAlgorithm,
)

ITEMS = {
    "favorite_color": "blue",
    "pet": "a Blue parrot",
    "goal": "buy a house",
}


def test_satisfies_search_algorithm_protocol():
    assert isinstance(LexicalSearch(), SearchAlgorithm)


async def test_blank_query_returns_empty():
    assert await LexicalSearch().search(ITEMS, "   ") == []


async def test_no_match_returns_empty():
    assert await LexicalSearch().search(ITEMS, "zzz") == []


async def test_exact_key_match_ranks_first():
    hits = await LexicalSearch().search(ITEMS, "favorite_color")
    assert hits[0][0] == "favorite_color"


async def test_case_insensitive_value_match():
    hits = await LexicalSearch().search(ITEMS, "BLUE")
    keys = {key for key, _value, _score in hits}
    assert {"favorite_color", "pet"} <= keys
    assert "goal" not in keys


async def test_key_hit_outranks_value_only_hit():
    items = {"blue": "unrelated note", "pet": "a blue parrot"}
    hits = await LexicalSearch().search(items, "blue")
    assert hits[0][0] == "blue"


async def test_top_k_limits_results():
    items = {f"k{i}": "blue" for i in range(10)}
    hits = await LexicalSearch().search(items, "blue", top_k=3)
    assert len(hits) == 3


async def test_fuzzy_fallback_catches_typo():
    items = {"hobby": "hiking"}
    hits = await LexicalSearch().search(items, "hikng")  # dropped the 'i'
    assert hits and hits[0][0] == "hobby"


async def test_config_is_tunable():
    strict = LexicalSearchConfig(fuzzy_threshold=0.99)
    lenient = LexicalSearchConfig(fuzzy_threshold=0.5)
    items = {"hobby": "hiking"}

    assert await LexicalSearch(strict).search(items, "hikes") == []
    assert await LexicalSearch(lenient).search(items, "hikes") != []


def test_default_config_used_when_none_given():
    assert LexicalSearch(None)._config == LexicalSearchConfig()
