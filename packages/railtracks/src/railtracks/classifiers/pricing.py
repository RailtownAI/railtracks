"""Decision cost from LiteLLM's pricing table (``litellm.model_cost``)."""

from __future__ import annotations

from collections.abc import Sequence

import litellm


def decision_cost(
    keys: Sequence[str], input_tokens: int | None, output_tokens: int | None
) -> float | None:
    """Price a decision call from the first ``litellm.model_cost`` entry matching a key.

    Output tokens are priced only when the entry lists an output price.

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
        for key in keys:
            entry = litellm.model_cost.get(key)
            if not entry or entry.get("input_cost_per_token") is None:
                continue
            cost = input_tokens * float(entry["input_cost_per_token"])
            output_price = entry.get("output_cost_per_token")
            if output_tokens is not None and output_price is not None:
                cost += output_tokens * float(output_price)
            return cost
    except (TypeError, ValueError):
        return None
    return None
