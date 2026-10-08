from __future__ import annotations

import os

import litellm

from ..transport._litellm import LiteLLMDecisionModel


class OpenAIDecisions(LiteLLMDecisionModel):
    """OpenAI's Decisions API, e.g. ``gpt-6-luna`` (public beta since 2026-10-06).

    Calls ``litellm.adecisions`` with ``openai/<model_name>``. litellm reads
    ``OPENAI_API_KEY`` (required) and takes the base URL from ``litellm.api_base``, then
    ``OPENAI_BASE_URL``, then ``OPENAI_API_BASE``. The input can be text, other JSON
    (sent as JSON text), or a list of user messages with ``input_text`` and
    ``input_image`` parts. Guide:
    https://developers.openai.com/api/docs/guides/decisions.

    Pricing counts input tokens only: the API bills input tokens alone, while
    ``litellm.model_cost`` lists ``gpt-6-luna`` at chat prices.
    """

    provider_prefix = "openai"
    provider_name = "openai"
    default_api_base = "https://api.openai.com/v1"
    api_base_env = "OPENAI_BASE_URL"
    api_key_env = "OPENAI_API_KEY"
    bills_output_tokens = False

    @property
    def api_base(self) -> str:
        """The base URL the next call goes to, resolved in litellm's order."""
        return (
            self._api_base
            or litellm.api_base
            or os.environ.get(self.api_base_env)
            or os.environ.get("OPENAI_API_BASE")
            or self.default_api_base
        )
