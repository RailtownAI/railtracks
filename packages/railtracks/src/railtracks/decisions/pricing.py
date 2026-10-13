"""Decision cost from LiteLLM's pricing table.

``litellm.model_cost`` is fetched from LiteLLM's repository at import, so entries can
disappear between releases (``openrouter/typesafe/jev-1.13`` did in October 2026).
When none of a model's keys is there, the catalog bundled with the installed litellm
wheel is tried instead.
"""

from __future__ import annotations

import functools
from collections.abc import Mapping, Sequence
from typing import Any

import litellm
from litellm.litellm_core_utils.get_model_cost_map import GetModelCostMap


def _load_bundled_cost_map() -> Mapping[str, Any]:
    return GetModelCostMap.load_local_model_cost_map()


@functools.cache
def _bundled_cost_map() -> Mapping[str, Any]:
    """litellm's bundled catalog, read once; empty if it cannot be read."""
    try:
        return _load_bundled_cost_map()
    except Exception:
        return {}


def _price(
    entry: Mapping[str, Any], input_tokens: int, output_tokens: int | None
) -> float:
    cost = input_tokens * float(entry["input_cost_per_token"])
    output_price = entry.get("output_cost_per_token")
    if output_tokens is not None and output_price is not None:
        cost += output_tokens * float(output_price)
    return cost


def _find(catalog: Mapping[str, Any], keys: Sequence[str]) -> Mapping[str, Any] | None:
    for key in keys:
        entry = catalog.get(key)
        if entry and entry.get("input_cost_per_token") is not None:
            return entry
    return None


def decision_cost(
    keys: Sequence[str], input_tokens: int | None, output_tokens: int | None
) -> float | None:
    """Price a decision call from the first pricing-table entry matching a key.

    ``litellm.model_cost`` is searched first, then litellm's bundled catalog. Output
    tokens are priced only when the entry lists an output price.

    Args:
        keys: The pricing-table keys to try, in order.
        input_tokens: The input tokens the provider reported, if any.
        output_tokens: The output tokens the provider reported, if any.

    Returns:
        The cost in USD, or None when no key matches, the input tokens are unknown,
        or the entry is malformed. Never raises.
    """
    if input_tokens is None:
        return None
    try:
        entry = _find(litellm.model_cost, keys) or _find(_bundled_cost_map(), keys)
        return _price(entry, input_tokens, output_tokens) if entry else None
    except (TypeError, ValueError, AttributeError):
        return None
