from __future__ import annotations

from ..transport._litellm import LiteLLMDecisionModel


class OpenRouterAI(LiteLLMDecisionModel):
    """System One models through OpenRouter's decisions endpoint.

    Model ids carry the vendor, e.g. ``typesafe/jev-1.13``; calls
    ``litellm.adecisions`` with ``openrouter/<model_name>``. litellm reads
    ``OPENROUTER_API_KEY`` (required) and, optionally, ``OPENROUTER_API_BASE``. Text and
    JSON input only.
    """

    provider_prefix = "openrouter"
    provider_name = "openrouter"
    default_api_base = "https://openrouter.ai/api"
    api_base_env = "OPENROUTER_API_BASE"
    api_key_env = "OPENROUTER_API_KEY"
    pricing_prefixes = ("openrouter",)
