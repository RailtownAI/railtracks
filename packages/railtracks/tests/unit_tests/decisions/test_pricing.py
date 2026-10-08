"""Decision cost lookup against litellm.model_cost."""

import litellm
import pytest
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
