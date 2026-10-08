from __future__ import annotations

from ..transport._litellm import LiteLLMDecisionModel


class TypeSafeAI(LiteLLMDecisionModel):
    """TypeSafe's hosted System One models, e.g. ``jev-latest``.

    Calls ``litellm.adecisions`` with ``typesafe/<model_name>``. litellm reads
    ``TYPESAFE_API_KEY`` (required) and, optionally, ``TYPESAFE_API_BASE``. Text and
    JSON input only. API: https://docs.typesafe.ai/api.
    """

    provider_prefix = "typesafe"
    provider_name = "typesafe"
    default_api_base = "https://api.typesafe.ai"
    api_base_env = "TYPESAFE_API_BASE"
    api_key_env = "TYPESAFE_API_KEY"
    pricing_prefixes = ("typesafe",)
