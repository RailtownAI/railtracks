"""Decision cost through litellm's public pricing API, as the ``llm`` module prices chat.

Used only when litellm did not price the call itself (``response_cost``). A model
litellm does not list is unpriced (``None``) rather than an error.
"""

from __future__ import annotations

from collections.abc import Sequence

import litellm


def decision_cost(
    keys: Sequence[str], input_tokens: int | None, output_tokens: int | None
) -> float | None:
    """Price a decision call with ``litellm.cost_per_token`` for the first known key.

    Output tokens are priced only when given and only at the entry's output price.

    Args:
        keys: The model names to try, in order.
        input_tokens: The input tokens the provider reported, if any.
        output_tokens: The output tokens to bill, or None when the API bills none.

    Returns:
        The cost in USD, or None when the input tokens are unknown or litellm prices
        none of the keys. Never raises.
    """
    if input_tokens is None:
        return None
    for key in keys:
        try:
            prompt_cost, completion_cost = litellm.cost_per_token(
                model=key,
                prompt_tokens=input_tokens,
                completion_tokens=output_tokens or 0,
            )
            return float(prompt_cost) + float(completion_cost)
        except Exception:
            continue
    return None
