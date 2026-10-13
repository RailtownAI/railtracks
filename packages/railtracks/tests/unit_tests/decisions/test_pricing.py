"""Decision cost lookup against litellm.model_cost."""

import litellm
import pytest
from railtracks.decisions import pricing
from railtracks.decisions.pricing import decision_cost


def test_first_matching_key_wins():
    cost = decision_cost(["typesafe/nope", "typesafe/jev-latest"], 1000, None)
    assert cost == pytest.approx(1000 * 4.2e-08)


def test_no_matching_key_is_none():
    assert decision_cost(["typesafe/kev-4b", "kev-4b"], 1000, 10) is None


def test_missing_input_tokens_is_none():
    assert decision_cost(["typesafe/jev-latest"], None, 10) is None


def test_output_tokens_priced_when_listed(monkeypatch):
    monkeypatch.setitem(
        litellm.model_cost,
        "typesafe/priced",
        {"input_cost_per_token": 1e-06, "output_cost_per_token": 2e-06},
    )
    assert decision_cost(["typesafe/priced"], 100, 10) == pytest.approx(1.2e-04)
    assert decision_cost(["typesafe/priced"], 100, None) == pytest.approx(1e-04)


def test_output_tokens_ignored_without_price():
    # jev lists no output price; output tokens are free per the API docs
    cost = decision_cost(["typesafe/jev-latest"], 100, 20)
    assert cost == pytest.approx(100 * 4.2e-08)


def test_malformed_entry_never_raises(monkeypatch):
    monkeypatch.setitem(
        litellm.model_cost, "typesafe/broken", {"input_cost_per_token": "x"}
    )
    assert decision_cost(["typesafe/broken"], 100, None) is None


# ================= Bundled catalog fallback =================


@pytest.fixture
def bundled(monkeypatch):
    """Replace litellm's bundled catalog with a small dict."""
    entries: dict = {}
    monkeypatch.setattr(pricing, "_bundled_cost_map", lambda: entries)
    return entries


def test_bundled_catalog_used_when_the_live_one_lacks_the_model(bundled, monkeypatch):
    monkeypatch.delitem(litellm.model_cost, "typesafe/gone", raising=False)
    bundled["typesafe/gone"] = {"input_cost_per_token": 4.2e-08}
    assert decision_cost(["typesafe/gone"], 100, None) == pytest.approx(100 * 4.2e-08)


def test_live_catalog_wins_over_the_bundled_one(bundled, monkeypatch):
    monkeypatch.setitem(
        litellm.model_cost, "typesafe/both", {"input_cost_per_token": 1e-06}
    )
    bundled["typesafe/both"] = {"input_cost_per_token": 9e-06}
    assert decision_cost(["typesafe/both"], 100, None) == pytest.approx(1e-04)


def test_any_live_key_wins_before_the_bundled_catalog(bundled, monkeypatch):
    # the first key only in the bundled catalog, the second in the live one
    bundled["openrouter/typesafe/x"] = {"input_cost_per_token": 9e-06}
    monkeypatch.setitem(
        litellm.model_cost, "typesafe/x", {"input_cost_per_token": 1e-06}
    )
    cost = decision_cost(["openrouter/typesafe/x", "typesafe/x"], 100, None)
    assert cost == pytest.approx(1e-04)


def test_unreadable_bundled_catalog_is_none(monkeypatch):
    def broken():
        raise OSError("missing")

    monkeypatch.setattr(pricing, "_load_bundled_cost_map", broken)
    pricing._bundled_cost_map.cache_clear()
    try:
        assert decision_cost(["typesafe/kev-4b"], 100, None) is None
    finally:
        pricing._bundled_cost_map.cache_clear()


def test_real_bundled_catalog_prices_jev_on_openrouter(monkeypatch):
    # the entry the remote catalog dropped is still in the pinned wheel's copy
    monkeypatch.delitem(
        litellm.model_cost, "openrouter/typesafe/jev-1.13", raising=False
    )
    monkeypatch.delitem(litellm.model_cost, "typesafe/jev-1.13", raising=False)
    monkeypatch.delitem(litellm.model_cost, "jev-1.13", raising=False)
    cost = decision_cost(
        ["openrouter/typesafe/jev-1.13", "typesafe/jev-1.13", "jev-1.13"], 296, 73
    )
    assert cost == pytest.approx(296 * 4.2e-08)
