from __future__ import annotations

from ..transport._litellm import LiteLLMDecisionModel


class OpenAIDecisions(LiteLLMDecisionModel):
    """OpenAI's Decisions API, e.g. ``gpt-6-luna`` (public beta since 2026-10-06).

    Calls ``litellm.adecisions`` with ``openai/<model_name>``. litellm reads
    ``OPENAI_API_KEY`` (required) and, optionally, ``OPENAI_BASE_URL``. The input can be
    text, other JSON (sent as JSON text), or a list of user messages with
    ``input_text`` and ``input_image`` parts. Guide:
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
