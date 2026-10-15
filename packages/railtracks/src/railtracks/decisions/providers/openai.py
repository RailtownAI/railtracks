from __future__ import annotations

from typing import Any

import litellm

from ..model import DecisionModel


class OpenAIDecisions(DecisionModel):
    """OpenAI's Decisions API, e.g. ``gpt-6-luna`` (public beta since 2026-10-06).

    Calls ``litellm.adecisions`` with ``openai/<model_name>``. litellm reads the key
    from ``litellm.api_key``, then ``litellm.openai_key``, then ``OPENAI_API_KEY`` (one
    is required), and the base URL from ``litellm.api_base``, then ``OPENAI_BASE_URL``,
    then ``OPENAI_API_BASE``. Text and JSON input only. Guide:
    https://developers.openai.com/api/docs/guides/decisions.

    The cost counts input tokens only: the API bills input tokens alone, while
    ``litellm.model_cost`` lists ``gpt-6-luna`` at chat prices.
    """

    provider_prefix = "openai"
    provider_name = "openai"

    def _cost(self, response: Any, input_tokens: int | None) -> float | None:
        """``input_tokens`` at litellm's input price; None if litellm does not list the
        model. Never raises."""
        if input_tokens is None:
            return None
        try:
            input_cost, _ = litellm.cost_per_token(
                model=self.model_name, prompt_tokens=input_tokens, completion_tokens=0
            )
        except Exception:
            return None
        return float(input_cost)
